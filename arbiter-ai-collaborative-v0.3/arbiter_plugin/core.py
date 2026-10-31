"""Deterministic decision evaluation; no provider, network, or domain dependencies."""
from __future__ import annotations
import math
from collections import Counter
from collections.abc import Callable
from .models import DecisionRequest, DecisionResult, OptionScore, Option


def disagreement_entropy(request: DecisionRequest) -> float:
    """Vote dispersion, not probability of error; abstentions are excluded."""
    responses = [op.option_id for op in request.opinions if op.option_id is not None]
    if len(responses) <= 1:
        return 0.0
    counts = Counter(responses)
    if len(counts) == 1:
        return 0.0
    raw = -sum((n/len(responses)) * math.log2(n/len(responses)) for n in counts.values())
    maximum = math.log2(min(len(request.options), len(responses)))
    return min(1.0, raw/maximum) if maximum else 0.0


def _option_base(request: DecisionRequest, option) -> float:
    if option.expected_utility is not None:
        return option.expected_utility
    if request.criterion_weights and sum(request.criterion_weights.values()) > 0:
        numerator = sum(option.criterion_scores.get(k, 0.0) * w for k, w in request.criterion_weights.items())
        return numerator / sum(request.criterion_weights.values())
    return 0.0  # Consensus-only decision has no claimed numeric utility.


def evaluate_decision(request: DecisionRequest,
                      reputation: dict[str, float] | None = None,
                      *,
                      utility_fn: Callable[[DecisionRequest, Option], float] | None = None,
                      feasibility_fn: Callable[[DecisionRequest, Option], bool] | None = None
                      ) -> DecisionResult:
    """Returns a proposal only. It never executes actions or makes LLM calls.

    Optional hooks let domain-specific applications provide values/constraints,
    without importing those applications into the core. Hook values must use
    request.utility_unit; never silently convert dollars into rubric points.
    reputation: independently measured success rate by agent_id; [0,1].
    Self-reported confidence NEVER multiplies vote weight.
    """
    reputation = reputation or {}
    known_rep = {op.agent_id: max(0.0, min(1.0, reputation.get(op.agent_id, 0.5))) for op in request.opinions}
    votes = {o.id: 0.0 for o in request.options}
    for opinion in request.opinions:
        if opinion.option_id is None:
            continue
        c = opinion.confidence if opinion.confidence_source == 'calibrated' else 1.0
        votes[opinion.option_id] += known_rep[opinion.agent_id] * c

    scored: list[OptionScore] = []
    notes: list[str] = []
    for opt in request.options:
        base = float(utility_fn(request, opt)) if utility_fn else _option_base(request, opt)
        if not math.isfinite(base):
            raise ValueError('Utility hook must produce a finite number')
        policy_pass = bool(feasibility_fn(request, opt)) if feasibility_fn else True
        feasible = opt.feasible and policy_pass and (request.maximum_risk_loss is None or opt.risk_loss <= request.maximum_risk_loss)
        scored.append(OptionScore(option_id=opt.id, base_utility=base,
            execution_cost=opt.execution_cost, risk_penalty=request.risk_aversion * opt.risk_loss,
            net_utility=base - opt.execution_cost - request.risk_aversion*opt.risk_loss,
            feasible=feasible, votes=votes[opt.id]))

    if request.mode == 'consensus':
        ordered = sorted(scored, key=lambda s: (not s.feasible, -s.votes, -s.net_utility, s.option_id))
        if not request.opinions or not any(votes.values()):
            notes.append('No usable agent votes; consensus ranking falls back to supplied utility / option id')
    else:
        ordered = sorted(scored, key=lambda s: (not s.feasible, -s.net_utility, -s.votes, s.option_id))
        if request.opinions and ordered[0].votes < max(votes.values()):
            notes.append('Highest-utility proposal differs from most-supported opinion; review evidence')
    best = next((x for x in ordered if x.feasible), None)
    if best is None:
        notes.append('No feasible option; nothing selected')
        status = 'no_feasible_option'
    elif request.require_human_review or any(op.risk_flag for op in request.opinions):
        notes.append('Human approval required or risk flag present; no autonomous execution')
        status = 'needs_review'
    else:
        status = 'proposed'
    if any(op.confidence_source == 'self_report' for op in request.opinions):
        notes.append('Self-reported confidence excluded from voting weights')
    if not request.opinions:
        notes.append('No agent opinions supplied; ranks depend only on user-provided inputs')
    return DecisionResult(decision_id=request.decision_id, status=status,
        selected_option_id=best.option_id if best else None,
        mode=request.mode, utility_unit=request.utility_unit,
        disagreement_entropy=disagreement_entropy(request), scores=ordered,
        agent_reputation_used=known_rep, notes=notes)
