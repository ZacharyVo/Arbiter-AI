import asyncio
import pytest
from pydantic import ValidationError
from arbiter_plugin import (BrainstormRequest, IdeaDraft, Contribution, Position,
                            CritiqueDraft, RoundTrace, InformationEstimate,
                            ScriptedBrainstormAgent, run_brainstorm, consolidate_brainstorm)


def test_new_idea_and_dissent_stay_visible():
    req = BrainstormRequest(session_id='s', objective='choose', max_discussion_rounds=1)
    traces = [
      RoundTrace(round_number=0, phase='independent', contributions=[
        Contribution(agent_id='a', new_ideas=[IdeaDraft(id='A', title='A', description='A', expected_utility=70, execution_cost=20, risk_loss=2, feasible=True)], position=Position(support_ids=['A'])),
        Contribution(agent_id='b', new_ideas=[IdeaDraft(id='B', title='B', description='B', expected_utility=85, execution_cost=25, risk_loss=20, feasible=True)], position=Position(support_ids=['B']))]),
      RoundTrace(round_number=1, phase='discussion', contributions=[
        Contribution(agent_id='c', new_ideas=[IdeaDraft(id='C', title='C', description='synthesis', parent_ids=['A','B'], expected_utility=95, execution_cost=10, risk_loss=5, feasible=True)], position=Position(support_ids=['C'])),
        Contribution(agent_id='b', position=Position(support_ids=['B'], oppose_ids=['A']))])]
    r = consolidate_brainstorm(req, traces)
    assert {i.id for i in r.ideas} == {'A', 'B', 'C'}
    assert r.selected_idea_id == 'C'
    assert r.status == 'proposed'
    assert r.dissents[0].idea_id == 'A'
    assert r.dissents[0].supporters == ['a'] and r.dissents[0].opponents == ['b']
    assert r.ideas[-1].parent_ids == ['A', 'B']


def test_unscored_new_idea_blocks_fake_final_decision():
    req = BrainstormRequest(session_id='s', objective='choose')
    traces = [RoundTrace(round_number=0, phase='independent', contributions=[
        Contribution(agent_id='x', new_ideas=[IdeaDraft(id='new', title='New', description='unknown cost')])])]
    r = consolidate_brainstorm(req, traces)
    assert r.status == 'needs_estimates' and r.selected_idea_id is None
    assert r.unscored_ids == ['new'] and r.provisional_leader_id is None


def test_agent_unsupported_verified_values_rejected():
    req = BrainstormRequest(session_id='s', objective='choose')
    traces = [RoundTrace(round_number=0, phase='independent', contributions=[
       Contribution(agent_id='a', new_ideas=[IdeaDraft(id='a', title='A', description='a', values_source='independently_verified')])])]
    with pytest.raises(ValueError, match='Agent-generated'):
        consolidate_brainstorm(req, traces)


def test_unknown_critique_and_position_rejected():
    req = BrainstormRequest(session_id='s', objective='choose')
    with pytest.raises(ValueError, match='Critique target unknown'):
        consolidate_brainstorm(req, [RoundTrace(round_number=0, phase='independent', contributions=[Contribution(agent_id='a', critiques=[CritiqueDraft(target_id='fake', claim='bad')])])])
    with pytest.raises(ValueError, match='Position points'):
        consolidate_brainstorm(req, [RoundTrace(round_number=0, phase='independent', contributions=[Contribution(agent_id='a', position=Position(support_ids=['fake']))])])


def test_duplicate_ids_and_cycle():
    req = BrainstormRequest(session_id='s', objective='choose')
    draft = IdeaDraft(id='X', title='X', description='test')
    with pytest.raises(ValueError, match='Duplicate idea'):
        consolidate_brainstorm(req, [RoundTrace(round_number=0, phase='independent', contributions=[Contribution(agent_id='a', new_ideas=[draft]), Contribution(agent_id='b', new_ideas=[draft])])])
    with pytest.raises(ValueError, match='cycle'):
        consolidate_brainstorm(req, [RoundTrace(round_number=0, phase='independent', contributions=[Contribution(agent_id='a', new_ideas=[IdeaDraft(id='A', title='A', description='a', parent_ids=['B']),IdeaDraft(id='B', title='B', description='b', parent_ids=['A'])])])])


def test_nonfinite_scores_and_negative_cost_rejected():
    with pytest.raises(ValidationError):
        IdeaDraft(id='X', title='X', description='x', expected_utility=float('nan'))
    with pytest.raises(ValidationError):
        IdeaDraft(id='X', title='X', description='x', execution_cost=-1)


def test_vois_stop_without_forcing_consensus():
    from examples.collaborative_demo import create_demo
    req, agents = create_demo()
    r = asyncio.run(run_brainstorm(req, agents))
    assert r.stop_reason == 'information_not_worth_cost'
    assert r.selected_idea_id == 'hybrid'
    assert len(r.dissents) == 3
    assert len(r.traces) == 3
    assert r.status == 'needs_review'


def test_budget_preflight_blocks_agents():
    req = BrainstormRequest(session_id='s', objective='choose', max_api_budget_usd=.01)
    a = ScriptedBrainstormAgent('a', Contribution(agent_id='a'), reserved_api_cost_usd=.01)
    b = ScriptedBrainstormAgent('b', Contribution(agent_id='b'), reserved_api_cost_usd=.01)
    r = asyncio.run(run_brainstorm(req, [a,b]))
    assert r.stop_reason == 'estimated_budget_insufficient' and r.traces == []


def test_no_novel_ideas_stops_early():
    req = BrainstormRequest(session_id='s', objective='choose', max_discussion_rounds=5)
    a = ScriptedBrainstormAgent('a', Contribution(agent_id='a', new_ideas=[IdeaDraft(id='A', title='a', description='a')]))
    b = ScriptedBrainstormAgent('b', Contribution(agent_id='b'))
    r = asyncio.run(run_brainstorm(req, [a,b]))
    assert r.stop_reason == 'no_new_ideas' and len(r.traces) == 2


def test_one_malformed_contribution_does_not_erase_other_agents():
    req = BrainstormRequest(session_id='s', objective='choose', max_discussion_rounds=0)
    good = ScriptedBrainstormAgent('good', Contribution(agent_id='good', new_ideas=[IdeaDraft(id='OK', title='OK', description='okay')]))
    bad = ScriptedBrainstormAgent('bad', Contribution(agent_id='bad', position=Position(support_ids=['not_found'])))
    r = asyncio.run(run_brainstorm(req, [good,bad]))
    assert [idea.id for idea in r.ideas] == ['OK']
    assert r.traces[0].errors and r.traces[0].contributions[0].agent_id == 'good'


def test_reported_cost_exceeding_estimate_requires_review():
    req = BrainstormRequest(session_id='s', objective='choose', max_api_budget_usd=.03, max_discussion_rounds=0)
    a = ScriptedBrainstormAgent('a', Contribution(agent_id='a', new_ideas=[IdeaDraft(id='A', title='A', description='a', expected_utility=9, execution_cost=1, risk_loss=1, feasible=True)], reported_cost_usd=.06))
    b = ScriptedBrainstormAgent('b', Contribution(agent_id='b'))
    r = asyncio.run(run_brainstorm(req, [a,b]))
    assert r.stop_reason == 'budget_exceeded' and r.status == 'needs_review'
    assert r.reported_api_spent_usd == .06


def test_deterministic_repeated_offline_results():
    from examples.collaborative_demo import create_demo
    req, agents = create_demo()
    a = asyncio.run(run_brainstorm(req, agents))
    b = asyncio.run(run_brainstorm(req, agents))
    assert a.model_dump() == b.model_dump()


def test_independent_agents_cannot_anticipate_other_agent_ideas():
    req = BrainstormRequest(session_id='s', objective='choose')
    traces = [RoundTrace(round_number=0, phase='independent', contributions=[
      Contribution(agent_id='a', new_ideas=[IdeaDraft(id='A', title='A', description='a')]),
      Contribution(agent_id='b', new_ideas=[IdeaDraft(id='B', title='B', description='b')],
                   position=Position(oppose_ids=['A']))])]
    with pytest.raises(ValueError, match='not yet visible'):
        consolidate_brainstorm(req, traces)


def test_http_adapter_transcript_and_invalid_reference():
    from fastapi.testclient import TestClient
    from arbiter_plugin.api import create_app
    client = TestClient(create_app())
    req = {"session_id": "web", "objective": "compare"}
    valid = {"request": req, "traces": [{"round_number": 0, "phase": "independent", "contributions": [{"agent_id": "a", "new_ideas": [{"id": "A", "title": "A", "description": "a"}]}]}]}
    got = client.post('/v1/brainstorm', json=valid)
    assert got.status_code == 200 and got.json()['ideas'][0]['id'] == 'A'
    invalid = {"request": req, "traces": [{"round_number": 0, "phase": "independent", "contributions": [{"agent_id": "a", "position": {"support_ids": ["ghost"]}}]}]}
    resp = client.post('/v1/brainstorm', json=invalid)
    assert resp.status_code == 422
