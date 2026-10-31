"""Optional MCP adapter: deterministic scoring of host-submitted brainstorm transcripts."""
from __future__ import annotations
import os
from typing import Any
from .models import DecisionRequest, ResearchRequest, VerifiedOutcome
from .core import evaluate_decision
from .information import plan_information
from .feedback import FeedbackStore
from .collaboration import BrainstormRequest, RoundTrace, consolidate_brainstorm
from .adaptive import NextActionEstimate, select_next_action
from .value_learning import InformationValueLearner, LearningRequest, VerifiedValueObservation


def create_mcp_server():
    from mcp.server import MCPServer  # optional official SDK v2
    server = MCPServer('PluralForge AI', instructions=(
        'Collect independent ideas and multiple rounds of open-ended discussion. '
        'Preserve dissent and unscored ideas; propose only, do not execute actions.'))

    @server.tool()
    def arbiter_brainstorm(payload: dict[str, Any]) -> dict[str, Any]:
        """Consolidate host-collected agent proposals/critiques; no meta-judge or forced consensus."""
        req = BrainstormRequest.model_validate(payload['request'])
        traces = [RoundTrace.model_validate(t) for t in payload.get('traces', [])]
        return consolidate_brainstorm(req, traces).model_dump(mode='json')

    @server.tool()
    def pluralforge_plan_next_step(payload: dict[str, Any]) -> dict[str, Any]:
        """Select next Agent/retrieval/stop from explicit, externally supplied utility forecasts."""
        action = select_next_action(
            [NextActionEstimate.model_validate(x) for x in payload.get('forecasts', [])],
            remaining_api_budget_usd=float(payload['remaining_api_budget_usd']),
            reservations_usd=payload.get('agent_reservations_usd', {}),
            retriever_available=payload.get('retriever_available', False))
        return action.model_dump(mode='json')

    @server.tool()
    def arbiter_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        """Score explicitly supplied options using deterministic utility and risk constraints."""
        req = DecisionRequest.model_validate(payload)
        store = FeedbackStore(os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite'))
        return evaluate_decision(req, store.reliability(req.domain)).model_dump(mode='json')

    @server.tool()
    def arbiter_plan_research(payload: dict[str, Any]) -> dict[str, Any]:
        """Evaluate supplied information-value estimate vs cost."""
        return plan_information(ResearchRequest.model_validate(payload)).model_dump(mode='json')

    @server.tool()
    def arbiter_record_verified_outcome(payload: dict[str, Any], confirm_record: bool = False) -> dict[str, Any]:
        """Record verified outcome in local SQLite only after explicit approval."""
        if not confirm_record:
            raise ValueError('Explicit confirmation required: confirm_record=true')
        return FeedbackStore(os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite')).record(
            VerifiedOutcome.model_validate(payload)).model_dump(mode='json')
    @server.tool()
    def pluralforge_value_forecast(payload: dict[str, Any]) -> dict[str, Any]:
        """Forecast marginal information value from *previously verified* logged outcomes.

        No model is called and no further step is executed.
        """
        req = LearningRequest.model_validate(payload)
        return InformationValueLearner(os.getenv('PLURALFORGE_VALUE_DB',
            'pluralforge_value_feedback.sqlite')).forecast(req).model_dump(mode='json')

    @server.tool()
    def pluralforge_value_next_step(payload: dict[str, Any]) -> dict[str, Any]:
        """Recommend one next action using learned gains, explicit evidence and API budget."""
        store = InformationValueLearner(os.getenv('PLURALFORGE_VALUE_DB',
            'pluralforge_value_feedback.sqlite'))
        result = store.recommend(LearningRequest.model_validate(payload['request']),
            remaining_api_budget_usd=float(payload['remaining_api_budget_usd']),
            reservations_usd=payload.get('agent_reservations_usd',{}),
            retriever_available=bool(payload.get('retriever_available',False)),
            minimum_net_gain=float(payload.get('minimum_net_gain',0)))
        return result.model_dump(mode='json')

    @server.tool()
    def pluralforge_record_value_feedback(payload: dict[str, Any],
                                         confirm_verified: bool = False) -> dict[str, Any]:
        """Only explicitly confirmed, evidence-attributed feedback is persisted locally."""
        store = InformationValueLearner(os.getenv('PLURALFORGE_VALUE_DB',
            'pluralforge_value_feedback.sqlite'))
        added = store.record(VerifiedValueObservation.model_validate(payload),
                             confirm_verified=confirm_verified)
        return {'recorded': added}

    return server


def main():
    create_mcp_server().run(transport='stdio')

if __name__ == '__main__':
    main()
