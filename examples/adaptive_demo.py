"""Adaptive two-agent follow-up example; all agent responses are scripted.

Phase 0: all agents propose independently.
Phase 1: one creative agent is consulted to propose a hybrid.
Phase 2: a critic is consulted; dissent survives.
Phase 3: host predicts further discussion has negative net value and stops.
"""
import asyncio
from examples.collaborative_demo import create_demo
from pluralforge import NextActionEstimate, run_brainstorm


def forecast(action, gain, cost, api_usd, agent_id=None):
    return NextActionEstimate(action=action, agent_id=agent_id,
        expected_decision_gain=gain, execution_cost_utility=cost,
        estimated_api_cost_usd=api_usd,
        rationale='Scripted host estimate in utility points, not model-calibrated')


async def main():
    req, agents = create_demo()
    result = await run_brainstorm(req, agents, adaptive_forecasts={
        1: [forecast('discuss_all', 10, 6, .06),
            forecast('consult_agent', 9, 2, .02, 'creative')],
        2: [forecast('consult_agent', 5, 1, .02, 'quality')],
        3: [forecast('discuss_all', 1, 3, .06)],
    })
    print('PLURALFORGE AI — SCRIPTED DEMO, NOT LIVE MODELS')
    for step in result.traces:
        route = step.route_decision
        print(f'Round {step.round_number}: {step.phase} / '
              f'{route.action if route else "initial_all_agents"} / '
              f'new ideas={step.new_ids}')
    print('Provisional leader:', result.provisional_leader_id)
    print('Status:', result.status, '/ Stop:', result.stop_reason)
    print('Dissent:', [(d.idea_id, d.supporters, d.opponents) for d in result.dissents])
    print('Reported API cost (scripted):', round(result.reported_api_spent_usd,5))


if __name__ == '__main__':
    asyncio.run(main())
