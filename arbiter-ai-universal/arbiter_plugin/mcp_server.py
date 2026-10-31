"""MCP v2 adapter. Requires `pip install -e .[mcp]`. No remote actions."""
from __future__ import annotations
import os
from typing import Any
from .models import DecisionRequest, ResearchRequest, VerifiedOutcome
from .core import evaluate_decision
from .information import plan_information
from .feedback import FeedbackStore


def create_mcp_server():
    from mcp.server import MCPServer  # official SDK v2, optional dependency
    server = MCPServer('Arbiter AI Universal',
        instructions='Propose options using supplied data; never execute the selected action. All scores must be sourced or explicitly estimated.')

    @server.tool()
    def arbiter_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        """Rank options and report multi-agent disagreement, constraints and review status. Never executes."""
        req = DecisionRequest.model_validate(payload)
        path = os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite')
        result = evaluate_decision(req, FeedbackStore(path).reliability(req.domain))
        return result.model_dump(mode='json')

    @server.tool()
    def arbiter_plan_research(payload: dict[str, Any]) -> dict[str, Any]:
        """Recommend whether more information is worth its opportunity and estimated API cost."""
        return plan_information(ResearchRequest.model_validate(payload)).model_dump(mode='json')

    @server.tool()
    def arbiter_record_verified_outcome(payload: dict[str, Any], confirm_record: bool = False) -> dict[str, Any]:
        """Locally record independently verified outcome; requires explicit confirmation and citation."""
        if not confirm_record:
            raise ValueError('Explicit confirmation required: confirm_record=true')
        receipt = FeedbackStore(os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite')).record(
            VerifiedOutcome.model_validate(payload))
        return receipt.model_dump(mode='json')
    return server


def main():
    server = create_mcp_server()
    server.run(transport='stdio')

if __name__ == '__main__':
    main()
