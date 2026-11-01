import pytest
from pydantic import ValidationError
from pluralforge import (
    ExperimentEstimate, NextActionEstimate, select_research_or_experiment
)

def f(action='retrieve', gain=7, cost=3, usd=.01):
    return NextActionEstimate(action=action, expected_decision_gain=gain,
        execution_cost_utility=cost, estimated_api_cost_usd=usd,
        rationale='explicit host forecast')

def e(gain=11, cost=2, usd=.1, name='trial-1'):
    return ExperimentEstimate(experiment_id=name, expected_decision_gain=gain,
        execution_cost_utility=cost, estimated_execution_cost_usd=usd,
        rationale='host hypothesis', candidate_ref='git:abc', benchmark_ref='test:one')

def route(forecasts=None, experiments=None, **kw):
    args = dict(forecasts=[f()] if forecasts is None else forecasts,
        experiments=[e()] if experiments is None else experiments,
        remaining_api_budget_usd=.05, remaining_experiment_budget_usd=.5,
        reservations_usd={}, retriever_available=True,
        experiment_runner_available=True, human_approved_experiments=frozenset({'trial-1'}))
    args.update(kw)
    return select_research_or_experiment(**args)

def test_experiment_beats_retrieval_given_approval():
    r=route()
    assert r.action == 'run_experiment' and r.target_id == 'trial-1'
    assert r.predicted_net_gain == 9

def test_unapproved_experiment_cannot_run():
    r=route(human_approved_experiments=frozenset())
    assert r.action=='retrieve'
    assert any(x.reason=='experiment_not_approved' for x in r.ranked_actions)

def test_missing_sandbox_and_budget_block_experiment():
    assert route(experiment_runner_available=False).action == 'retrieve'
    assert route(remaining_experiment_budget_usd=.01).action == 'retrieve'

def test_separate_cash_budgets():
    assert route(remaining_api_budget_usd=0).action == 'run_experiment'
    assert route(remaining_experiment_budget_usd=0).action == 'retrieve'

def test_unprofitable_experiment_stops():
    r=route(forecasts=[],experiments=[e(gain=1,cost=2)])
    assert r.action == 'stop'

def test_validation_and_duplicate_ids():
    with pytest.raises(ValueError):
        route(experiments=[e(),e()])
    with pytest.raises(ValueError):
        route(remaining_experiment_budget_usd=-1)
    with pytest.raises(ValidationError):
        e(gain=float('nan'))

def test_no_forecast_means_stop():
    assert route(forecasts=[],experiments=[]).action == 'stop'
