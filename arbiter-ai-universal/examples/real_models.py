"""Live LLM demo. Deliberately opt-in; provider calls incur charges."""
import asyncio
import os
from arbiter_plugin import DecisionRequest, Option, evaluate_decision
from arbiter_plugin.llm_adapters import AgentSpec, ask_parallel

async def main():
    models = [x.strip() for x in os.environ.get('ARBITER_MODELS', '').split(',') if x.strip()]
    if not models:
        raise SystemExit('Set ARBITER_MODELS to valid LiteLLM model IDs, then run again; API charges apply.')
    req = DecisionRequest(decision_id='live-demo', objective='Choose a software feature release strategy',
       domain='software', mode='consensus', options=[
           Option(id='ship_now', description='Release small tested MVP with feedback loop'),
           Option(id='delay', description='Delay release until a larger redesign is complete')])
    specs = [AgentSpec(agent_id=f'agent_{i}', model=model) for i, model in enumerate(models, 1)]
    opinions = await ask_parallel(req, specs, concurrency=3)
    req.opinions = opinions.opinions
    print('Failed agents:', [e.__dict__ for e in opinions.failures])
    print('Estimated API spend:', opinions.total_cost_usd_estimate)
    print(evaluate_decision(req).model_dump_json(indent=2))

if __name__ == '__main__':
    asyncio.run(main())
