"""Offline demonstration: verified examples -> learned forecasts -> budget-aware route.

All numbers are hand-created fixtures, not model performance or actual VOI.
No provider calls. No data is written to a user's home directory.
"""
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from pathlib import Path

from pluralforge import (InformationValueLearner, LearningContext, ActionCandidate,
                         VerifiedValueObservation, LearningRequest)


def main():
    base=datetime(2025,1,1,tzinfo=timezone.utc)
    ctx=LearningContext(domain='software',utility_unit='points',tags={'task':'architecture'})
    with TemporaryDirectory() as folder:
        store=InformationValueLearner(Path(folder)/'learn.sqlite')
        candidates=[ActionCandidate(action='consult_agent', agent_id='critic'),
                    ActionCandidate(action='discuss_all'), ActionCandidate(action='retrieve')]
        for i in range(6):
            for name, candidate, gain, cost, api in [
                ('critic',candidates[0],12,2,.02),
                ('team',candidates[1],10,6,.06),
                ('search',candidates[2],7,3,.03)]:
                obs=VerifiedValueObservation(
                    observation_id=f'{name}-{i}',decision_id=f'decision-{name}-{i}',
                    context=ctx,candidate=candidate,score_before=40,score_after=40+gain,
                    execution_cost_utility=cost,api_cost_usd=api,
                    occurred_at=base+timedelta(days=i),
                    available_at=base+timedelta(days=i+1),
                    verifier='fixture-generator',evidence_ref=f'synthetic://case/{name}/{i}')
                store.record(obs,confirm_verified=True)
        req=LearningRequest(context=ctx,candidates=candidates,as_of=base+timedelta(days=20))
        result=store.recommend(req,remaining_api_budget_usd=.05,
              reservations_usd={'critic':.02,'designer':.04},retriever_available=True)
        print('Historical feedback: 18 synthetic host-attested observations')
        print('Forecasted actions (utility points, API cost in USD):')
        for f in result.report.forecasts:
            print(f'  {f.action:14} {str(f.agent_id):9} source={f.source:7} '
                  f'gain={f.conservative_gain:.2f} cost={f.predicted_cost_utility:.2f} '
                  f'api=${f.predicted_api_cost_usd:.3f}')
        print('Recommended action:', result.route.action, result.route.agent_id or '')
        print('Predicted net gain:', round(result.route.predicted_net_gain,2))
        print('Important: observed correlations are not proven causal value of information.')


if __name__ == '__main__':
    main()
