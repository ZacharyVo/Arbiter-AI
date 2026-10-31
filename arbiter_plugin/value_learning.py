"""Information Value Learning Engine (IVLE).

Learns *observed*, evidence-attributed marginal decision utility for an action
from past logged interventions. This is predictive association, NOT causal VOI:
only executed actions have outcomes and the host supplies comparable utilities.

Safety invariants:
* A historical observation is eligible only after evidence became available.
* Missing/sparse evidence abstains rather than inventing an expected gain.
* Dollars and domain-defined utility points are never subtracted from each other.
* A human/host must explicitly verify outcomes before recording them.
* An action forecast does not trigger API calls or approve side effects.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .adaptive import NextActionEstimate, RouteDecision, select_next_action

ActionType = Literal['discuss_all', 'consult_agent', 'retrieve']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Datetime must have an explicit timezone')
    return value.astimezone(timezone.utc)


class LearningContext(Strict):
    domain: str = Field(min_length=1, max_length=80)
    utility_unit: str = Field(default='points', min_length=1, max_length=80)
    tags: dict[str, str] = Field(default_factory=dict, description='Non-sensitive categorical context features')

    @model_validator(mode='after')
    def check_tags(self):
        if len(self.tags) > 12 or any(not k or not v or len(k)>80 or len(v)>80 for k,v in self.tags.items()):
            raise ValueError('Use at most 12 short, non-empty categorical tags')
        return self


class ActionCandidate(Strict):
    action: ActionType
    agent_id: str | None = None

    @model_validator(mode='after')
    def check_target(self):
        if self.action == 'consult_agent' and not self.agent_id:
            raise ValueError('consult_agent requires agent_id')
        if self.action != 'consult_agent' and self.agent_id is not None:
            raise ValueError('Only consult_agent can carry agent_id')
        return self


class VerifiedValueObservation(Strict):
    """Host-attested realized before/after *decision* scores, same rubric and unit.

    available_at: when the verified evidence became accessible (anti-lookahead).
    This is a host assertion, NOT cryptographic verification.
    """
    observation_id: str = Field(min_length=1, max_length=150)
    decision_id: str = Field(min_length=1, max_length=150)
    context: LearningContext
    candidate: ActionCandidate
    score_before: float
    score_after: float
    execution_cost_utility: float = Field(ge=0)
    api_cost_usd: float = Field(ge=0)
    occurred_at: datetime
    available_at: datetime
    verifier: str = Field(min_length=1, max_length=150)
    evidence_ref: str = Field(min_length=1, max_length=500)
    notes: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def chronology(self):
        if _utc(self.available_at) < _utc(self.occurred_at):
            raise ValueError('available_at must not precede occurred_at')
        return self

    @property
    def observed_gain(self) -> float:
        return self.score_after - self.score_before


class LearningRequest(Strict):
    context: LearningContext
    candidates: list[ActionCandidate] = Field(min_length=1, max_length=100)
    as_of: datetime
    min_weighted_support: float = Field(default=3.0, ge=1)
    prior_strength: float = Field(default=2.0, ge=0)
    uncertainty_penalty: float = Field(default=1.0, ge=0)
    other_context_weight: float = Field(default=0.25, ge=0, le=1)
    # Explicit host estimates used ONLY when empirical evidence is too sparse.
    host_priors: list[NextActionEstimate] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_request(self):
        _utc(self.as_of)
        ids = [(c.action, c.agent_id) for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate action candidate')
        prior_ids = [(c.action, c.agent_id) for c in self.host_priors]
        if len(prior_ids) != len(set(prior_ids)):
            raise ValueError('Duplicate host prior')
        return self


class ActionForecast(Strict):
    action: ActionType
    agent_id: str | None = None
    source: Literal['learned', 'host_prior', 'insufficient_data']
    observation_count: int = 0
    exact_context_count: int = 0
    weighted_support: float = 0.0
    raw_mean_gain: float | None = None
    uncertainty_standard_error: float | None = None
    conservative_gain: float | None = None
    predicted_cost_utility: float | None = None
    predicted_api_cost_usd: float | None = None
    rationale: str


class LearningReport(Strict):
    context: LearningContext
    as_of: datetime
    forecasts: list[ActionForecast]
    usable_estimates: list[NextActionEstimate]
    notes: list[str] = Field(default_factory=list)


class LearningRoute(Strict):
    report: LearningReport
    route: RouteDecision


class InformationValueLearner:
    """SQLite-backed, domain- and utility-unit-isolated estimator.

    Uses verified observed gains and shrinkage toward zero (conservative prior).
    Observational sample selection is NOT corrected; no causal or policy-value
    claims should be made on this estimator's outputs alone.
    """
    def __init__(self, db_path: str | Path = 'pluralforge_value_feedback.sqlite'):
        self.path = str(db_path)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute('PRAGMA busy_timeout = 10000')
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS value_observations (
                observation_id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                utility_unit TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                action TEXT NOT NULL,
                agent_id TEXT,
                score_before REAL NOT NULL,
                score_after REAL NOT NULL,
                execution_cost_utility REAL NOT NULL,
                api_cost_usd REAL NOT NULL,
                occurred_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                verifier TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_value_history ON value_observations(domain,utility_unit,available_at,action,agent_id)')

    def record(self, observation: VerifiedValueObservation, *, confirm_verified: bool = False) -> bool:
        """Persist only after explicit human/host verification assertion.

        Returns False on exact duplicate; conflicting IDs raise ValueError.
        """
        if not confirm_verified:
            raise PermissionError('Explicit verified-feedback confirmation is required')
        payload = observation.model_dump(mode='json')
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        with self._connect() as db:
            old = db.execute('SELECT payload_json FROM value_observations WHERE observation_id=?',
                             (observation.observation_id,)).fetchone()
            if old is not None:
                if old[0] != canonical:
                    raise ValueError('Conflicting observation_id; refusing overwrite')
                return False
            db.execute('''INSERT INTO value_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                observation.observation_id, observation.decision_id, observation.context.domain,
                observation.context.utility_unit,
                json.dumps(observation.context.tags, sort_keys=True, ensure_ascii=False),
                observation.candidate.action, observation.candidate.agent_id,
                observation.score_before, observation.score_after,
                observation.execution_cost_utility, observation.api_cost_usd,
                _utc(observation.occurred_at).isoformat(), _utc(observation.available_at).isoformat(),
                observation.verifier, observation.evidence_ref, canonical))
        return True

    def _history(self, context: LearningContext, as_of: datetime):
        # Compare UTC ISO timestamps with consistent format; a cutoff is strict.
        with self._connect() as db:
            rows = db.execute('''SELECT action,agent_id,tags_json,score_before,score_after,
                execution_cost_utility,api_cost_usd,decision_id FROM value_observations
                WHERE domain=? AND utility_unit=? AND available_at < ?''', (
                context.domain, context.utility_unit, _utc(as_of).isoformat())).fetchall()
        return rows

    def forecast(self, request: LearningRequest) -> LearningReport:
        history = self._history(request.context, request.as_of)
        priors = {(p.action, p.agent_id): p for p in request.host_priors}
        results: list[ActionForecast] = []
        estimates: list[NextActionEstimate] = []
        # Prevent a series of repeated feedback records from the same decision
        # artificially raising support (they may be correlated).
        for candidate in request.candidates:
            key = (candidate.action, candidate.agent_id)
            selected = [r for r in history if (r[0],r[1])==key]
            seen_decisions: set[str] = set()
            usable = []
            for r in selected:
                if r[7] in seen_decisions:
                    continue
                seen_decisions.add(r[7])
                same_context = json.loads(r[2]) == request.context.tags
                w = 1.0 if same_context else request.other_context_weight
                if w > 0:
                    usable.append((w, r[4]-r[3], r[5], r[6], same_context))
            support = sum(x[0] for x in usable)
            exact_n = sum(1 for x in usable if x[4])
            if support >= request.min_weighted_support:
                # Shrink the expected gain toward zero, never an unsupported high prior.
                gain = sum(w*g for w,g,_,_,_ in usable) / (support + request.prior_strength)
                # Weighted variance is descriptive. Conservative uncertainty uses
                # n_eff to avoid treating fractional weights as independent samples.
                empirical = sum(w*g for w,g,_,_,_ in usable) / support
                variance = sum(w*(g-empirical)**2 for w,g,_,_,_ in usable) / support
                n_eff = support**2 / sum(w*w for w,*_ in usable)
                stderr = math.sqrt(variance / n_eff)
                conservative = max(0.0, gain - request.uncertainty_penalty * stderr)
                cost = sum(w*c for w,_,c,_,_ in usable)/support
                api = sum(w*u for w,_,_,u,_ in usable)/support
                forecast = ActionForecast(action=candidate.action, agent_id=candidate.agent_id,
                    source='learned', observation_count=len(usable), exact_context_count=exact_n,
                    weighted_support=support, raw_mean_gain=gain,
                    uncertainty_standard_error=stderr, conservative_gain=conservative,
                    predicted_cost_utility=cost, predicted_api_cost_usd=api,
                    rationale=f'Historical observed gains; shrinkage={request.prior_strength:g}; not causal VOI.')
                estimates.append(NextActionEstimate(action=candidate.action,agent_id=candidate.agent_id,
                    expected_decision_gain=conservative, execution_cost_utility=cost,
                    estimated_api_cost_usd=api, rationale=forecast.rationale,estimated_by='value_learning_engine'))
            elif key in priors:
                p=priors[key]
                forecast = ActionForecast(action=candidate.action,agent_id=candidate.agent_id,
                    source='host_prior',observation_count=len(usable),exact_context_count=exact_n,
                    weighted_support=support,conservative_gain=p.expected_decision_gain,
                    predicted_cost_utility=p.execution_cost_utility,
                    predicted_api_cost_usd=p.estimated_api_cost_usd,
                    rationale='Insufficient verified history: explicit host prior used, not a learned estimate.')
                estimates.append(p)
            else:
                forecast=ActionForecast(action=candidate.action,agent_id=candidate.agent_id,
                    source='insufficient_data',observation_count=len(usable),exact_context_count=exact_n,
                    weighted_support=support,
                    rationale='Insufficient verified history and no host estimate: abstain from forecasting.')
            results.append(forecast)
        return LearningReport(context=request.context,as_of=request.as_of,
            forecasts=results,usable_estimates=estimates,
            notes=['Observed outcomes are not counterfactual causal effects; selection bias may exist.',
                   'Decision utility and API USD remain separate units.',
                   'Eligibility uses strictly earlier evidence-availability dates; verify host-attested metadata.',
                   'Sparse actions abstain unless an explicit host prior is supplied.'])

    def recommend(self, request: LearningRequest, *, remaining_api_budget_usd: float,
                  reservations_usd: dict[str,float], retriever_available: bool=False,
                  minimum_net_gain: float=0) -> LearningRoute:
        report = self.forecast(request)
        route = select_next_action(report.usable_estimates,
            remaining_api_budget_usd=remaining_api_budget_usd,
            reservations_usd=reservations_usd,
            retriever_available=retriever_available,
            minimum_net_gain=minimum_net_gain)
        return LearningRoute(report=report, route=route)
