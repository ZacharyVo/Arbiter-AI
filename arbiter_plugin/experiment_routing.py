"""Advisory unified next-step routing; no autonomous experiment execution."""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from .adaptive import NextActionEstimate, select_next_action


class ExperimentEstimate(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    experiment_id: str = Field(min_length=1, max_length=80)
    expected_decision_gain: float = Field(ge=0)
    execution_cost_utility: float = Field(ge=0)
    estimated_execution_cost_usd: float = Field(ge=0)
    rationale: str = Field(min_length=1)
    benchmark_ref: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)


class UnifiedActionRank(BaseModel):
    action: str
    target_id: str | None
    net_information_value: float
    eligible: bool
    reason: str
    required_api_usd: float = 0
    required_experiment_usd: float = 0


class UnifiedRoute(BaseModel):
    action: str
    target_id: str | None = None
    predicted_net_gain: float = 0
    reason: str
    ranked_actions: list[UnifiedActionRank] = Field(default_factory=list)


def select_research_or_experiment(
    forecasts: list[NextActionEstimate], *,
    experiments: list[ExperimentEstimate],
    remaining_api_budget_usd: float,
    remaining_experiment_budget_usd: float,
    reservations_usd: dict[str, float],
    retriever_available: bool = False,
    experiment_runner_available: bool = False,
    human_approved_experiments: frozenset[str] = frozenset(),
    minimum_net_gain: float = 0,
) -> UnifiedRoute:
    """Compare next-step forecasts against independent cash and utility limits.

    Experiment eligibility requires an explicitly approved experiment ID,
    available sandbox and sufficient execution budget. The function only plans.
    Existing verified-history learner forecasts can be passed as forecasts.
    """
    if remaining_experiment_budget_usd < 0 or minimum_net_gain < 0:
        raise ValueError('Budget and minimum net gain must be nonnegative')
    if len({e.experiment_id for e in experiments}) != len(experiments):
        raise ValueError('Duplicate experiment IDs')
    base = select_next_action(forecasts,
        remaining_api_budget_usd=remaining_api_budget_usd,
        reservations_usd=reservations_usd,
        retriever_available=retriever_available,
        minimum_net_gain=minimum_net_gain)
    ranks = [UnifiedActionRank(
        action=r.action, target_id=r.agent_id,
        net_information_value=r.net_information_value, eligible=r.eligible,
        reason=r.reason, required_api_usd=r.required_api_reservation_usd)
        for r in base.ranked_actions]
    for e in experiments:
        net = e.expected_decision_gain - e.execution_cost_utility
        if e.experiment_id not in human_approved_experiments:
            reason = 'experiment_not_approved'
        elif not experiment_runner_available:
            reason = 'experiment_runner_unavailable'
        elif e.estimated_execution_cost_usd > remaining_experiment_budget_usd + 1e-12:
            reason = 'experiment_budget_insufficient'
        elif net <= minimum_net_gain:
            reason = 'nonpositive_marginal_value'
        else:
            reason = 'eligible'
        ranks.append(UnifiedActionRank(
            action='run_experiment', target_id=e.experiment_id,
            net_information_value=net, eligible=reason == 'eligible',
            reason=reason, required_experiment_usd=e.estimated_execution_cost_usd))
    ranks.sort(key=lambda r: (-r.net_information_value,
        r.required_api_usd + r.required_experiment_usd, r.action, r.target_id or ''))
    top = next((r for r in ranks if r.eligible), None)
    return UnifiedRoute(
        action=top.action if top else 'stop',
        target_id=top.target_id if top else None,
        predicted_net_gain=top.net_information_value if top else 0,
        reason='highest_eligible_net_value' if top else 'no_eligible_positive_gain',
        ranked_actions=ranks)
