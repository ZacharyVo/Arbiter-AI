"""OPTIONAL paid-provider example. Nothing is called until explicitly run."""
from __future__ import annotations
import asyncio
import os
from arbiter_plugin import BrainstormRequest, LiteLLMBrainstormAgent, run_brainstorm


async def main():
    models = [m.strip() for m in os.environ.get('ARBITER_MODELS', '').split(',') if m.strip()]
    if len(models) < 2:
        raise SystemExit('Set ARBITER_MODELS to at least 2 LiteLLM model IDs. Provider API keys required.')
    budget = float(os.environ.get('ARBITER_API_BUDGET_USD', '0.25'))
    reserve = float(os.environ.get('ARBITER_CALL_RESERVATION_USD', '0.04'))
    objective = os.environ.get('ARBITER_OBJECTIVE', 'How can a small open-source team improve code review?')
    agents = [LiteLLMBrainstormAgent(agent_id=f'agent{i+1}', model=m,
               instructions=perspective, reserved_api_cost_usd=reserve)
              for i, (m, perspective) in enumerate(zip(models,
                  ['Prioritize simple implementation and low maintenance.',
                   'Prioritize robustness, accessibility and counterarguments.'] +
                  ['Seek new combinations and highlight unknowns.'] * max(0, len(models) - 2)))]
    req = BrainstormRequest(session_id='live-example', objective=objective,
                            max_discussion_rounds=1, max_api_budget_usd=budget,
                            require_human_review=True)
    result = await run_brainstorm(req, agents)
    print(result.model_dump_json(indent=2))
    # New ideas without values remain unscored; no hidden judge invents numbers.


if __name__ == '__main__':
    asyncio.run(main())
