"""Chronological observed-action forecast evaluation, offline and deterministic.

Does NOT estimate counterfactual policy lift or compare unobserved alternatives.
A forecast is made before each held-out outcome is added to the SQLite store.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from pluralforge import (InformationValueLearner, LearningContext, ActionCandidate,
                         VerifiedValueObservation, LearningRequest)


def evaluate():
    ctx=LearningContext(domain='example',utility_unit='points',tags={'task':'planning'})
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    actions=[ActionCandidate(action='consult_agent',agent_id='reviewer'),
             ActionCandidate(action='retrieve')]
    observed_gains={'consult_agent':[9,11,8,10,9,12,10,8,11,10,9,11],
                    'retrieve':[5,6,4,7,5,4,6,5,7,5,4,6]}
    pred_errors=[]
    coverage=0
    holdout=0
    with TemporaryDirectory() as tmp:
        store=InformationValueLearner(Path(tmp)/'replay.sqlite')
        for index in range(12):
            t=start+timedelta(days=index*2)
            req=LearningRequest(context=ctx,candidates=actions,as_of=t,uncertainty_penalty=0)
            forecasts=store.forecast(req).forecasts
            if index >= 6:
                for f in forecasts:
                    holdout+=1
                    if f.source=='learned':
                        coverage+=1
                        pred_errors.append(abs(f.raw_mean_gain-observed_gains[f.action][index]))
            for action in actions:
                obs=VerifiedValueObservation(observation_id=f'{action.action}-{index}',
                    decision_id=f'{action.action}-{index}',context=ctx,candidate=action,
                    score_before=25,score_after=25+observed_gains[action.action][index],
                    execution_cost_utility=2 if action.action=='consult_agent' else 1,
                    api_cost_usd=.02 if action.action=='consult_agent' else .01,
                    occurred_at=t,available_at=t+timedelta(days=1),
                    verifier='synthetic-fixture',evidence_ref=f'synthetic:day-{index}')
                store.record(obs,confirm_verified=True)
    return {'kind':'synthetic_logged_action_temporal_replay',
            'held_out_observed_action_samples':holdout,
            'forecast_coverage':round(coverage/holdout,4),
            'mean_absolute_error_points':round(sum(pred_errors)/len(pred_errors),4) if pred_errors else None,
            'causal_policy_improvement_proven':False,
            'data_leakage_policy':'observations become available the day after action, strictly before forecast as_of'}


def main():
    report=evaluate()
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
