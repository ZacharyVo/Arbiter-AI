"""Domain-neutral, disagreement-preserving collaborative decision orchestration.

No model acts as final judge. LLM outputs are proposals and critiques, never
verified evidence or automatic authorization to execute actions.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .adaptive import NextActionEstimate, RouteDecision, select_next_action
from .novelty import NoveltyFlag, surface_duplicate_flags
from .value_learning import InformationValueLearner, LearningContext, ActionCandidate, LearningRequest


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class IdeaDraft(Strict):
    id: str = Field(min_length=1, max_length=120, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]*$')
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parent_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    # The values below are OPTIONAL estimates from the host / agent.
    # They must all be in the same user-declared utility unit.
    expected_utility: float | None = None
    execution_cost: float | None = Field(default=None, ge=0)
    risk_loss: float | None = Field(default=None, ge=0)
    feasible: bool | None = None  # None = not established
    values_source: Literal['host', 'agent_estimate', 'independently_verified'] = 'agent_estimate'

    @model_validator(mode='after')
    def check_ancestry(self):
        if self.id in self.parent_ids or len(self.parent_ids) != len(set(self.parent_ids)):
            raise ValueError('Idea cannot list itself or duplicate parent IDs')
        return self


class Idea(IdeaDraft):
    created_by: str
    created_in_round: int = Field(ge=0)


class CritiqueDraft(Strict):
    target_id: str
    claim: str = Field(min_length=1)
    severity: Literal['question', 'challenge', 'risk_warning'] = 'question'
    evidence: list[str] = Field(default_factory=list)


class Critique(CritiqueDraft):
    agent_id: str
    round_number: int


class Position(Strict):
    support_ids: list[str] = Field(default_factory=list)
    oppose_ids: list[str] = Field(default_factory=list)
    note: str = ''

    @model_validator(mode='after')
    def no_conflicts(self):
        if set(self.support_ids) & set(self.oppose_ids):
            raise ValueError('Position cannot support and oppose the same idea')
        return self


class Contribution(Strict):
    agent_id: str
    new_ideas: list[IdeaDraft] = Field(default_factory=list)
    critiques: list[CritiqueDraft] = Field(default_factory=list)
    position: Position = Field(default_factory=Position)
    public_summary: str = ''
    reported_cost_usd: float | None = Field(default=None, ge=0)


class InformationEstimate(Strict):
    """Optional *externally estimated* marginal value of another discussion round."""
    expected_decision_gain: float = Field(ge=0)
    discussion_cost_utility: float = Field(ge=0)
    estimated_api_cost_usd: float = Field(default=0, ge=0)


class BrainstormRequest(Strict):
    session_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    domain: str = 'general'
    utility_unit: str = 'points'
    seed_ideas: list[IdeaDraft] = Field(default_factory=list)
    max_discussion_rounds: int = Field(default=2, ge=0, le=12)
    stop_after_no_new_rounds: int = Field(default=1, ge=1)
    max_total_ideas: int = Field(default=40, ge=1)
    max_api_budget_usd: float = Field(default=1.0, ge=0)
    initial_api_spent_usd: float = Field(default=0.0, ge=0)
    risk_aversion: float = Field(default=1.0, ge=0)
    maximum_risk_loss: float | None = Field(default=None, ge=0)
    require_human_review: bool = False
    round_information_estimates: dict[int, InformationEstimate] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_seeds(self):
        if len({i.id for i in self.seed_ideas}) != len(self.seed_ideas):
            raise ValueError('Duplicate seed idea IDs')
        if len(self.seed_ideas) > self.max_total_ideas:
            raise ValueError('Seed ideas exceed max_total_ideas')
        if self.initial_api_spent_usd > self.max_api_budget_usd:
            raise ValueError('Initial API spend exceeds budget')
        if any(k < 1 or k > self.max_discussion_rounds for k in self.round_information_estimates):
            raise ValueError('Information estimate keys must be discussion rounds within range')
        for idea in self.seed_ideas:
            if any(p not in {x.id for x in self.seed_ideas} for p in idea.parent_ids):
                raise ValueError('Seed idea references an unknown parent')
        return self


class DiscussionView(Strict):
    session_id: str
    objective: str
    domain: str
    utility_unit: str
    round_number: int
    ideas: list[Idea]
    critiques: list[Critique]
    latest_positions: dict[str, Position]
    research_observations: list['ResearchObservation'] = Field(default_factory=list)


class ResearchObservation(Strict):
    source_ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    reported_cost_usd: float = Field(default=0, ge=0)
    evidence_status: Literal['unverified', 'host_checked'] = 'unverified'


class RoundTrace(Strict):
    round_number: int
    phase: Literal['independent', 'discussion', 'research']
    research_observations: list[ResearchObservation] = Field(default_factory=list)
    route_decision: RouteDecision | None = None
    unattributed_api_cost_usd: float = Field(default=0, ge=0)
    contributions: list[Contribution] = Field(default_factory=list)
    new_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    reported_cost_usd: float = 0.0


class IdeaScore(Strict):
    idea_id: str
    net_utility: float
    expected_utility: float
    execution_cost: float
    risk_penalty: float
    feasible: bool
    values_source: str


class Dissent(Strict):
    idea_id: str
    supporters: list[str] = Field(default_factory=list)
    opponents: list[str] = Field(default_factory=list)


class BrainstormResult(Strict):
    session_id: str
    stop_reason: Literal['max_rounds', 'no_new_ideas', 'information_not_worth_cost',
                         'estimated_budget_insufficient', 'budget_exceeded', 'no_agents_responded']
    status: Literal['proposed', 'needs_review', 'needs_estimates', 'no_feasible_option']
    selected_idea_id: str | None = None
    provisional_leader_id: str | None = None
    ideas: list[Idea]
    critiques: list[Critique]
    latest_positions: dict[str, Position]
    dissents: list[Dissent]
    scores: list[IdeaScore]
    unscored_ids: list[str]
    traces: list[RoundTrace]
    research_observations: list[ResearchObservation] = Field(default_factory=list)
    novelty_flags: list[NoveltyFlag] = Field(default_factory=list)
    reported_api_spent_usd: float
    notes: list[str]


class BrainstormAgent(Protocol):
    agent_id: str
    # Preflight reservation; must be estimated externally and not assumed a hard limit.
    reserved_api_cost_usd: float

    async def propose(self, view: DiscussionView) -> Contribution: ...

    async def discuss(self, view: DiscussionView) -> Contribution: ...


def _score_ideas(req: BrainstormRequest, ideas: list[Idea], critiques: list[Critique], positions: dict[str, Position],
                 traces: list[RoundTrace], stop_reason: str, spent: float) -> BrainstormResult:
    scores: list[IdeaScore] = []
    unscored: list[str] = []
    notes: list[str] = []
    for idea in ideas:
        if (idea.expected_utility is None or idea.execution_cost is None or
                idea.risk_loss is None or idea.feasible is None):
            unscored.append(idea.id)
            continue
        feasible = idea.feasible and (req.maximum_risk_loss is None or idea.risk_loss <= req.maximum_risk_loss)
        scores.append(IdeaScore(idea_id=idea.id, net_utility=idea.expected_utility - idea.execution_cost - req.risk_aversion * idea.risk_loss,
                                expected_utility=idea.expected_utility, execution_cost=idea.execution_cost,
                                risk_penalty=req.risk_aversion * idea.risk_loss, feasible=feasible, values_source=idea.values_source))
    scores.sort(key=lambda x: (not x.feasible, -x.net_utility, x.idea_id))
    feasible = [s for s in scores if s.feasible]
    leader = feasible[0].idea_id if feasible else None
    risk_warnings = [crit for crit in critiques if crit.severity == 'risk_warning']
    if unscored:
        status: str = 'needs_estimates'
        selected = None
        notes.append('No final selection: some proposals lack complete, comparable utility/cost/risk/feasibility estimates.')
    elif not feasible:
        status = 'no_feasible_option'
        selected = None
    elif req.require_human_review or risk_warnings or spent > req.max_api_budget_usd:
        status = 'needs_review'
        selected = leader
        notes.append('Risk warning, budget overrun or review policy requires human review; never auto-executes.')
    else:
        status = 'proposed'
        selected = leader
    all_ids = [i.id for i in ideas]
    dissents: list[Dissent] = []
    for idea_id in all_ids:
        supporters = sorted(a for a, p in positions.items() if idea_id in p.support_ids)
        opponents = sorted(a for a, p in positions.items() if idea_id in p.oppose_ids)
        if supporters and opponents:
            dissents.append(Dissent(idea_id=idea_id, supporters=supporters, opponents=opponents))
    if dissents:
        notes.append('Unresolved disagreements preserved; no forced consensus or judge override.')
    novelty_flags = surface_duplicate_flags(ideas)
    if novelty_flags:
        notes.append('Potential similar idea wording flagged; not deduplicated or semantically verified.')
    if any(s.values_source == 'agent_estimate' for s in scores):
        notes.append('Agent-supplied numeric estimates are unverified hypotheses, not measured outcomes.')
    if spent > req.max_api_budget_usd:
        notes.append('Reported spend exceeds budget: preflight reservations are not provider hard spending caps.')
    notes.append('This system proposes only; it never executes selected actions.')
    return BrainstormResult(session_id=req.session_id, stop_reason=stop_reason,
                            status=status, selected_idea_id=selected, provisional_leader_id=leader,
                            ideas=ideas, critiques=critiques, latest_positions=positions, dissents=dissents,
                            scores=scores, unscored_ids=unscored, traces=traces,
                            research_observations=[o for t in traces for o in t.research_observations],
                            novelty_flags=novelty_flags, reported_api_spent_usd=spent, notes=notes)


def consolidate_brainstorm(req: BrainstormRequest, traces: list[RoundTrace]) -> BrainstormResult:
    """Pure, offline reducer for transcript -> auditable ideas, dissent, scores.

    Useful as a Python SDK / MCP tool when the host itself runs LLMs. It rejects
    invalid proposal IDs and references without invoking any model or judge.
    """
    ideas: list[Idea] = [Idea(**draft.model_dump(exclude={'values_source'}), values_source=draft.values_source,
                              created_by='host', created_in_round=0) for draft in req.seed_ideas]
    known = {idea.id for idea in ideas}
    critiques: list[Critique] = []
    positions: dict[str, Position] = {}
    processed: list[RoundTrace] = []
    spent = req.initial_api_spent_usd
    for trace in traces:
        if not processed and (trace.round_number != 0 or trace.phase != 'independent'):
            raise ValueError('First trace must be independent round 0')
        if processed and trace.round_number <= processed[-1].round_number:
            raise ValueError('Traces must have increasing round_number')
        if trace.phase not in ({'independent'} if trace.round_number == 0 else {'discussion', 'research'}):
            raise ValueError('Round phase does not match round number')
        if trace.phase == 'research' and trace.contributions:
            raise ValueError('Research round cannot contain agent contributions')
        if trace.phase != 'research' and trace.research_observations:
            raise ValueError('Only research round can contain research observations')
        if trace.round_number > req.max_discussion_rounds:
            raise ValueError('Trace round exceeds configured maximum')
        ids_new: list[str] = []
        seen_agents: set[str] = set()
        for contrib in trace.contributions:
            if contrib.agent_id in seen_agents:
                raise ValueError('Duplicate agent contribution within a round')
            seen_agents.add(contrib.agent_id)
            for draft in contrib.new_ideas:
                if draft.id in known or draft.id in ids_new:
                    raise ValueError(f'Duplicate idea ID: {draft.id}')
                ids_new.append(draft.id)
                if len(known) + len(ids_new) > req.max_total_ideas:
                    raise ValueError('Too many ideas; max_total_ideas reached')
        all_known = known | set(ids_new)
        parent_graph = {i.id: i.parent_ids for i in ideas}
        parent_graph.update({draft.id: draft.parent_ids for c in trace.contributions for draft in c.new_ideas})
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(node: str):
            if node in visiting:
                raise ValueError('Parent links form a cycle')
            if node in visited:
                return
            visiting.add(node)
            for parent in parent_graph.get(node, []):
                if parent in parent_graph:
                    visit(parent)
            visiting.remove(node)
            visited.add(node)
        for node in parent_graph:
            visit(node)
        for contrib in trace.contributions:
            # A participant cannot react to a peer's idea before that peer's
            # parallel response is shared. Each phase sees earlier rounds + own output.
            participant_visible = known | {d.id for d in contrib.new_ideas}
            for draft in contrib.new_ideas:
                if any(pid not in participant_visible for pid in draft.parent_ids):
                    raise ValueError(f'Parent was not visible to {contrib.agent_id}: {draft.id}')
                # Agents cannot self-certify estimates as verified or host-supplied.
                if draft.values_source != 'agent_estimate':
                    raise ValueError('Agent-generated ideas must have values_source=agent_estimate')
                ideas.append(Idea(**draft.model_dump(), created_by=contrib.agent_id,
                                  created_in_round=trace.round_number))
            for crit in contrib.critiques:
                if crit.target_id not in participant_visible:
                    raise ValueError(f'Critique target unknown or not yet visible: {crit.target_id}')
                critiques.append(Critique(**crit.model_dump(), agent_id=contrib.agent_id,
                                         round_number=trace.round_number))
            choices = contrib.position.support_ids + contrib.position.oppose_ids
            if any(cid not in participant_visible for cid in choices):
                raise ValueError('Position points to unknown or not yet visible idea')
            positions[contrib.agent_id] = contrib.position
        known = all_known
        reported = (sum(c.reported_cost_usd or 0.0 for c in trace.contributions)
                    + sum(o.reported_cost_usd for o in trace.research_observations)
                    + trace.unattributed_api_cost_usd)
        # Trace reported cost is redundant: use contributions as source of truth.
        processed.append(trace.model_copy(update={'new_ids': ids_new, 'reported_cost_usd': reported}))
        spent += reported
    return _score_ideas(req, ideas, critiques, positions, processed, 'max_rounds', spent)


async def run_brainstorm(
    req: BrainstormRequest, agents: Sequence[BrainstormAgent], *,
    adaptive_forecasts: dict[int, list[NextActionEstimate]] | None = None,
    research_fn=None,
    value_learner: InformationValueLearner | None = None,
    learning_tags: dict[str, str] | None = None,
    learning_as_of: datetime | None = None,
    learning_min_weighted_support: float = 3.0,
) -> BrainstormResult:
    """Async independent generation -> collaborative discussion -> deterministic score.

    Errors are visible in round traces. Continuing is budget/VOI gated, but all
    For learned routing, outcomes must have been explicitly verified and available
    before `learning_as_of`. Sparse history stops rather than fabricates a forecast.
    Host-supplied adaptive_forecasts override learned routing when both provided.
    """
    if len(agents) < 2:
        raise ValueError('Collaborative mode needs at least two agents')
    ids = [a.agent_id for a in agents]
    if len(set(ids)) != len(ids):
        raise ValueError('Agent IDs must be unique')
    for a in agents:
        reserved = a.reserved_api_cost_usd
        if reserved < 0:
            raise ValueError('Agent cost reservation must be nonnegative')

    # Freeze forecast time for the entire session, avoiding within-run lookahead.
    forecast_as_of = learning_as_of or datetime.now(timezone.utc)
    traces: list[RoundTrace] = []
    stopped = 'max_rounds'
    no_new = 0

    async def batch(number: int, phase: Literal['independent', 'discussion'],
                    participants: Sequence[BrainstormAgent] | None = None,
                    route_decision: RouteDecision | None = None):
        snapshot = consolidate_brainstorm(req, traces)
        view = DiscussionView(session_id=req.session_id, objective=req.objective, domain=req.domain,
                              utility_unit=req.utility_unit, round_number=number,
                              ideas=snapshot.ideas, critiques=snapshot.critiques,
                              latest_positions=snapshot.latest_positions,
                              research_observations=snapshot.research_observations)
        async def one(agent: BrainstormAgent):
            try:
                result = await (agent.propose(view) if phase == 'independent' else agent.discuss(view))
                if result.agent_id != agent.agent_id:
                    raise ValueError('Agent returned mismatched agent_id')
                return result
            except Exception as exc:
                return f'{agent.agent_id}: {type(exc).__name__}: {str(exc)[:140]}'
        outputs = await asyncio.gather(*(one(a) for a in (participants if participants is not None else agents)))
        contributions = [r for r in outputs if isinstance(r, Contribution)]
        errors = [r for r in outputs if isinstance(r, str)]
        trace = RoundTrace(round_number=number, phase=phase, contributions=[], errors=errors, route_decision=route_decision)
        # Validate per agent so one bad response cannot erase other agents' ideas.
        # Reported API costs are counted even if that response is invalid.
        trace.reported_cost_usd = sum(x.reported_cost_usd or 0 for x in contributions)
        # Check the full parallel batch first. Agents can refer to ideas that
        # are introduced simultaneously by peers (in scripted/test workflows).
        candidate_all = trace.model_copy(update={'contributions': contributions})
        try:
            consolidate_brainstorm(req, traces + [candidate_all])
        except ValueError as whole_error:
            trace.errors.append(f'Full batch invalid; isolating contributions: {whole_error}')
            # Salvage valid agents without trusting the malformed batch.
            for contribution in contributions:
                candidate = trace.model_copy(update={'contributions': trace.contributions + [contribution]})
                try:
                    consolidate_brainstorm(req, traces + [candidate])
                except ValueError as exc:
                    trace.errors.append(f'{contribution.agent_id}: contribution rejected: {exc}')
                else:
                    trace.contributions.append(contribution)
        else:
            trace.contributions = contributions
        # Charge reported API cost even for rejected (but parsed) contributions.
        trace.unattributed_api_cost_usd = max(0, sum(x.reported_cost_usd or 0 for x in contributions)
                       - sum(x.reported_cost_usd or 0 for x in trace.contributions))
        preview = consolidate_brainstorm(req, traces + [trace])
        trace.new_ids = [i.id for i in preview.ideas if i.created_in_round == number]
        traces.append(trace)
        return len(trace.new_ids), len(trace.contributions)

    def spent():
        return req.initial_api_spent_usd + sum(t.reported_cost_usd for t in traces)

    def can_start(participants=None):
        pool = participants if participants is not None else agents
        return spent() + sum(a.reserved_api_cost_usd for a in pool) <= req.max_api_budget_usd + 1e-12

    if not can_start():
        # All seeded ideas remain auditable even when no call can be authorized.
        return _score_ideas(req, consolidate_brainstorm(req, []).ideas, [], {}, [],
                            'estimated_budget_insufficient', spent())
    _, initial_responses = await batch(0, 'independent')
    if initial_responses == 0:
        stopped = 'no_agents_responded'
    elif spent() > req.max_api_budget_usd:
        stopped = 'budget_exceeded'
    else:
        for number in range(1, req.max_discussion_rounds + 1):
            if adaptive_forecasts is not None or value_learner is not None:
                if adaptive_forecasts is not None:
                    forecasts = adaptive_forecasts.get(number, [])
                else:
                    candidates = [ActionCandidate(action='discuss_all')]
                    candidates.extend(ActionCandidate(action='consult_agent',agent_id=a.agent_id) for a in agents)
                    if research_fn is not None:
                        candidates.append(ActionCandidate(action='retrieve'))
                    learned = value_learner.forecast(LearningRequest(
                        context=LearningContext(domain=req.domain, utility_unit=req.utility_unit,
                                                tags=learning_tags or {}),
                        candidates=candidates, as_of=forecast_as_of,
                        min_weighted_support=learning_min_weighted_support))
                    forecasts = learned.usable_estimates
                route = select_next_action(forecasts,
                    remaining_api_budget_usd=max(0, req.max_api_budget_usd - spent()),
                    reservations_usd={a.agent_id: a.reserved_api_cost_usd for a in agents},
                    retriever_available=research_fn is not None)
                if route.action == 'stop':
                    stopped = ('estimated_budget_insufficient' if route.reason == 'all_actions_unavailable_or_over_budget'
                               else 'information_not_worth_cost')
                    break
                if route.action == 'retrieve':
                    snapshot = consolidate_brainstorm(req, traces)
                    view = DiscussionView(session_id=req.session_id, objective=req.objective,
                        domain=req.domain, utility_unit=req.utility_unit, round_number=number,
                        ideas=snapshot.ideas, critiques=snapshot.critiques,
                        latest_positions=snapshot.latest_positions,
                        research_observations=snapshot.research_observations)
                    try:
                        observation = await research_fn(view)
                        if not isinstance(observation, ResearchObservation):
                            raise ValueError('Retriever must return ResearchObservation')
                        trace = RoundTrace(round_number=number, phase='research',
                                           research_observations=[observation], route_decision=route)
                    except Exception as exc:
                        trace = RoundTrace(round_number=number, phase='research', route_decision=route,
                                           errors=[f'research: {type(exc).__name__}: {str(exc)[:140]}'])
                    traces.append(trace)
                    if spent() > req.max_api_budget_usd:
                        stopped = 'budget_exceeded'
                        break
                    continue
                selected_agents = ([a for a in agents if a.agent_id == route.agent_id]
                                   if route.action == 'consult_agent' else agents)
                if not can_start(selected_agents):
                    stopped = 'estimated_budget_insufficient'
                    break
                new_count, _ = await batch(number, 'discussion', selected_agents, route)
                if spent() > req.max_api_budget_usd:
                    stopped = 'budget_exceeded'
                    break
                if new_count:
                    no_new = 0
                else:
                    no_new += 1
                    if no_new >= req.stop_after_no_new_rounds:
                        stopped = 'no_new_ideas'
                        break
                continue
            estimate = req.round_information_estimates.get(number)
            if estimate and estimate.expected_decision_gain <= estimate.discussion_cost_utility:
                stopped = 'information_not_worth_cost'
                break
            if estimate and estimate.estimated_api_cost_usd > req.max_api_budget_usd - spent():
                stopped = 'estimated_budget_insufficient'
                break
            if not can_start():
                stopped = 'estimated_budget_insufficient'
                break
            new_count, _ = await batch(number, 'discussion')
            if spent() > req.max_api_budget_usd:
                stopped = 'budget_exceeded'
                break
            if new_count:
                no_new = 0
            else:
                no_new += 1
                if no_new >= req.stop_after_no_new_rounds:
                    stopped = 'no_new_ideas'
                    break
    result = consolidate_brainstorm(req, traces)
    return _score_ideas(req, result.ideas, result.critiques, result.latest_positions,
                        result.traces, stopped, result.reported_api_spent_usd)
