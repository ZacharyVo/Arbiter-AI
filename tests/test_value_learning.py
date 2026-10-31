"""Invariants for observational value-learning, not claims of causal uplift."""
from datetime import datetime, timezone, timedelta
import asyncio
import pytest
from pydantic import ValidationError

from pluralforge import (LearningContext, ActionCandidate, VerifiedValueObservation,
                         LearningRequest, InformationValueLearner, NextActionEstimate,
                         BrainstormRequest, Contribution, IdeaDraft, Position,
                         ScriptedBrainstormAgent, run_brainstorm)

BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)
CTX = LearningContext(domain='software',utility_unit='points',tags={'task':'architecture'})


def event(n, *, action='consult_agent', agent='a', before=40, after=50,
          ctx=CTX, when=BASE, available=None, cost=2, usd=.01, decision=None):
    return VerifiedValueObservation(observation_id=f'id-{n}',decision_id=decision or f'd-{n}',
       context=ctx, candidate=ActionCandidate(action=action, agent_id=agent if action=='consult_agent' else None),
       score_before=before,score_after=after,execution_cost_utility=cost,api_cost_usd=usd,
       occurred_at=when,available_at=available or when+timedelta(days=1),
       verifier='independent-review',evidence_ref=f'fixture:{n}')


def query(*candidates,ctx=CTX,when=BASE+timedelta(days=20),**kwargs):
    return LearningRequest(context=ctx,candidates=list(candidates),as_of=when,**kwargs)


def test_requires_explicit_confirmation(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    with pytest.raises(PermissionError): store.record(event(1))
    assert store.forecast(query(ActionCandidate(action='consult_agent',agent_id='a'))).usable_estimates==[]


def test_idempotency_and_conflict(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    e=event(1)
    assert store.record(e,confirm_verified=True) is True
    assert store.record(e,confirm_verified=True) is False
    with pytest.raises(ValueError,match='Conflicting'):
        store.record(event(1,after=99),confirm_verified=True)


def test_no_future_or_not_yet_available_information(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    for i in range(3):
        store.record(event(i,when=BASE,available=BASE+timedelta(days=10)),confirm_verified=True)
    cand=ActionCandidate(action='consult_agent',agent_id='a')
    before=store.forecast(query(cand,when=BASE+timedelta(days=10)))
    after=store.forecast(query(cand,when=BASE+timedelta(days=11)))
    assert before.forecasts[0].source == 'insufficient_data'
    assert after.forecasts[0].source == 'learned'


def test_domain_unit_and_context_features_are_respected(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    for i in range(4): store.record(event(i),confirm_verified=True)
    cand=ActionCandidate(action='consult_agent',agent_id='a')
    assert store.forecast(query(cand,ctx=LearningContext(domain='education',utility_unit='points'))).usable_estimates==[]
    assert store.forecast(query(cand,ctx=LearningContext(domain='software',utility_unit='usd'))).usable_estimates==[]
    # Mismatched tags only receive 0.25 each -> support=1; not enough.
    x=store.forecast(query(cand,ctx=LearningContext(domain='software',utility_unit='points',tags={'task':'art'})))
    assert x.forecasts[0].weighted_support==pytest.approx(1)
    assert x.forecasts[0].source=='insufficient_data'


def test_learned_routing_picks_observed_gain_over_cost(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    for i in range(5):
        store.record(event(f'a{i}',after=54),confirm_verified=True)  # gain=14, cost=2
        store.record(event(f'b{i}',agent='b',after=46,cost=3),confirm_verified=True)  # gain=6,cost=3
    cand=[ActionCandidate(action='consult_agent',agent_id=x) for x in ['a','b']]
    plan=store.recommend(query(*cand),remaining_api_budget_usd=.05,
                         reservations_usd={'a':.02,'b':.02})
    assert plan.route.action=='consult_agent' and plan.route.agent_id=='a'
    assert plan.report.forecasts[0].source=='learned'
    assert plan.report.forecasts[0].conservative_gain < 14 # regularized toward zero
    assert plan.route.predicted_net_gain > 0


def test_negative_observed_gain_does_not_yield_positive_route(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    for i in range(4): store.record(event(i,after=30),confirm_verified=True)
    x=store.recommend(query(ActionCandidate(action='consult_agent',agent_id='a')),
                      remaining_api_budget_usd=1,reservations_usd={'a':.01})
    assert x.report.forecasts[0].raw_mean_gain < 0
    assert x.report.forecasts[0].conservative_gain==0
    assert x.route.action=='stop'


def test_sparse_prior_fallback_and_fail_closed(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    a=ActionCandidate(action='consult_agent',agent_id='a')
    assert store.recommend(query(a),remaining_api_budget_usd=1,
                           reservations_usd={'a':0}).route.action=='stop'
    prior=NextActionEstimate(action='consult_agent',agent_id='a',expected_decision_gain=5,
        execution_cost_utility=2,estimated_api_cost_usd=.02,rationale='explicit expert input')
    res=store.forecast(query(a,host_priors=[prior]))
    assert res.forecasts[0].source=='host_prior'
    assert res.usable_estimates[0].estimated_by=='host'


def test_zero_variance_and_duplicate_decisions(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    for i in range(4):
        store.record(event(i,decision='repeated'),confirm_verified=True)
    x=store.forecast(query(ActionCandidate(action='consult_agent',agent_id='a')))
    assert x.forecasts[0].observation_count==1
    assert x.forecasts[0].source=='insufficient_data'


def test_utc_and_chronology_validation():
    with pytest.raises(ValidationError):
        query(ActionCandidate(action='retrieve'),when=datetime(2025,1,1))
    with pytest.raises(ValidationError):
        event(1,available=BASE-timedelta(seconds=1))
    with pytest.raises(ValidationError):
        event(1,after=float('nan'))


def test_learner_integrated_into_async_brainstorm(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    for i in range(4):
        store.record(event(i,after=70,cost=1,usd=.001),confirm_verified=True)
    a=ScriptedBrainstormAgent('a', Contribution(agent_id='a',new_ideas=[
        IdeaDraft(id='a',title='Proposal A',description='A solution',expected_utility=70,
                  execution_cost=5,risk_loss=5,feasible=True)],reported_cost_usd=.001),
        discussions={1:Contribution(agent_id='a',new_ideas=[
            IdeaDraft(id='c',title='New solution',description='Synthesized solution',parent_ids=['a'],
                      expected_utility=85,execution_cost=5,risk_loss=4,feasible=True)],
                      position=Position(support_ids=['c']),reported_cost_usd=.001)},
        reserved_api_cost_usd=.002)
    b=ScriptedBrainstormAgent('b',Contribution(agent_id='b',new_ideas=[
        IdeaDraft(id='b',title='Proposal B',description='Alternative',expected_utility=50,
                  execution_cost=4,risk_loss=5,feasible=True)],reported_cost_usd=.001),
        reserved_api_cost_usd=.002)
    req=BrainstormRequest(session_id='engine',objective='choose',domain='software',utility_unit='points',
                          max_discussion_rounds=2,max_api_budget_usd=.02)
    r=asyncio.run(run_brainstorm(req,[a,b],value_learner=store,
       learning_tags={'task':'architecture'},learning_as_of=BASE+timedelta(days=20)))
    assert r.traces[1].route_decision.action=='consult_agent'
    assert r.traces[1].route_decision.agent_id=='a'
    assert 'c' in [i.id for i in r.ideas]
    assert r.stop_reason in ('information_not_worth_cost','no_new_ideas')


def test_learned_no_history_stops_without_more_api_calls(tmp_path):
    store=InformationValueLearner(tmp_path/'store.sqlite')
    a=ScriptedBrainstormAgent('a',Contribution(agent_id='a',reported_cost_usd=.001),reserved_api_cost_usd=.002)
    b=ScriptedBrainstormAgent('b',Contribution(agent_id='b',reported_cost_usd=.001),reserved_api_cost_usd=.002)
    req=BrainstormRequest(session_id='none',objective='study',max_discussion_rounds=2)
    r=asyncio.run(run_brainstorm(req,[a,b],value_learner=store))
    assert len(r.traces)==1 and r.stop_reason=='information_not_worth_cost'


def test_http_learning_endpoints(tmp_path,monkeypatch):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from arbiter_plugin.api import create_app
    monkeypatch.setenv('PLURALFORGE_VALUE_DB',str(tmp_path/'api.sqlite'))
    client=TestClient(create_app())
    e=event(1).model_dump(mode='json')
    assert client.post('/v1/value/record',json={'observation':e}).status_code==403
    assert client.post('/v1/value/record',json={'observation':e,'confirm_verified':True}).json()['recorded'] is True
    payload=query(ActionCandidate(action='consult_agent',agent_id='a')).model_dump(mode='json')
    assert client.post('/v1/value/forecast',json=payload).json()['forecasts'][0]['source']=='insufficient_data'
    assert client.post('/v1/value/next-step',json={'request':payload,'remaining_api_budget_usd':.1,
        'agent_reservations_usd':{'a':.01}}).json()['route']['action']=='stop'
