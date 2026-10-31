"""Cost-aware action selection for collective intelligence.

The planner does *not* infer value-of-information from disagreement alone.
Forecasts are explicitly supplied assumptions and remain auditable. API spend
and decision-utility costs are different units and never subtracted directly.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class NextActionEstimate(Strict):
    """An ex-ante host estimate for a possible next action, not a measured outcome."""
    action: Literal['discuss_all', 'consult_agent', 'retrieve']
    agent_id: str | None = None
    expected_decision_gain: float = Field(ge=0, description='Marginal expected improvement in decision utility')
    execution_cost_utility: float = Field(ge=0, description='All marginal costs converted into same utility unit')
    estimated_api_cost_usd: float = Field(ge=0, description='API cash budget needed; independent unit')
    rationale: str = Field(min_length=1)
    estimated_by: str = 'host'

    @model_validator(mode='after')
    def target_valid(self):
        if self.action == 'consult_agent' and not self.agent_id:
            raise ValueError('consult_agent requires agent_id')
        if self.action != 'consult_agent' and self.agent_id is not None:
            raise ValueError('agent_id only allowed for consult_agent')
        return self


class ActionRank(Strict):
    action: str
    agent_id: str | None = None
    net_information_value: float
    required_api_reservation_usd: float
    eligible: bool
    reason: str
    rationale: str


class RouteDecision(Strict):
    """The decision is only a recommendation for the orchestrator to execute."""
    action: Literal['stop', 'discuss_all', 'consult_agent', 'retrieve']
    agent_id: str | None = None
    predicted_net_gain: float = 0
    expected_api_cost_usd: float = 0
    reason: str
    ranked_actions: list[ActionRank] = Field(default_factory=list)


def select_next_action(
    forecasts: list[NextActionEstimate], *, remaining_api_budget_usd: float,
    reservations_usd: dict[str, float], retriever_available: bool = False,
    minimum_net_gain: float = 0,
) -> RouteDecision:
    """Choose the highest positive net value that fits both budget and capability.

    `minimum_net_gain` is in decision utility, not dollars. Reserved costs are
    preflight planning estimates, **not** a hard provider spending limit.
    """
    if remaining_api_budget_usd < 0 or minimum_net_gain < 0:
        raise ValueError('Budget and minimum net gain must be nonnegative')
    if any(x < 0 for x in reservations_usd.values()):
        raise ValueError('Agent reservations must be nonnegative')
    rankings: list[ActionRank] = []
    for f in forecasts:
        reservation = (sum(reservations_usd.values()) if f.action == 'discuss_all'
                       else reservations_usd.get(f.agent_id, 0) if f.action == 'consult_agent' else 0)
        required = max(f.estimated_api_cost_usd, reservation)
        supported = (f.agent_id in reservations_usd if f.action == 'consult_agent'
                     else bool(reservations_usd) if f.action == 'discuss_all'
                     else retriever_available)
        net = f.expected_decision_gain - f.execution_cost_utility
        eligible = supported and required <= remaining_api_budget_usd + 1e-12 and net > minimum_net_gain
        reason = ('unsupported_action' if not supported else 'insufficient_budget'
                  if required > remaining_api_budget_usd + 1e-12 else 'nonpositive_marginal_value'
                  if net <= minimum_net_gain else 'eligible')
        rankings.append(ActionRank(action=f.action, agent_id=f.agent_id,
                                   net_information_value=net, required_api_reservation_usd=required,
                                   eligible=eligible, reason=reason, rationale=f.rationale))
    rankings.sort(key=lambda r: (-r.net_information_value, r.required_api_reservation_usd,
                                 r.action, r.agent_id or ''))
    winner = next((r for r in rankings if r.eligible), None)
    if winner:
        return RouteDecision(action=winner.action, agent_id=winner.agent_id,
                             predicted_net_gain=winner.net_information_value,
                             expected_api_cost_usd=winner.required_api_reservation_usd,
                             reason='highest_positive_net_value_within_budget', ranked_actions=rankings)
    reason = ('no_forecast' if not forecasts else 'all_actions_unavailable_or_over_budget'
              if any(r.reason in ('insufficient_budget', 'unsupported_action') for r in rankings)
              else 'no_positive_marginal_value')
    return RouteDecision(action='stop', reason=reason, ranked_actions=rankings)
