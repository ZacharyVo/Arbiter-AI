"""Policy-contract tests. Estimates are explicit, never secretly inferred."""
import asyncio
import pytest
from pydantic import ValidationError
from arbiter_plugin.adaptive import NextActionEstimate, select_next_action
from arbiter_plugin.collaboration import (
    BrainstormRequest, IdeaDraft, Contribution, Position, ResearchObservation,
    RoundTrace, consolidate_brainstorm, run_brainstorm,
)
from arbiter_plugin.brainstorm_agents import ScriptedBrainstormAgent


def f(action, gain, cost, usd, agent_id=None):
    return NextActionEstimate(action=action, agent_id=agent_id,
        expected_decision_gain=gain, execution_cost_utility=cost,
        estimated_api_cost_usd=usd, rationale='host assumption')


def test_router_chooses_highest_positive_net_value_not_most_divisive():
    r = select_next_action([f('discuss_all', 10, 9, .07),
                            f('consult_agent', 6, 1, .02, 'critical'),
                            f('retrieve', 12, 3, .04)],
                            remaining_api_budget_usd=.1,
                            reservations_usd={'critical': .02, 'other': .03},
                            retriever_available=True)
    assert r.action == 'retrieve' and r.predicted_net_gain == 9


def test_router_filters_unavailable_and_over_budget():
    r = select_next_action([f('retrieve', 50, 1, .01), f('consult_agent', 20, 1, .20, 'a')],
       remaining_api_budget_usd=.1, reservations_usd={'a':.02})
    assert r.action == 'stop'
    assert {x.reason for x in r.ranked_actions} == {'unsupported_action','insufficient_budget'}


def test_router_avoids_mixing_dollars_with_utility():
    r = select_next_action([f('consult_agent', 1, 2, 0, 'a')],
        remaining_api_budget_usd=1000, reservations_usd={'a':0})
    assert r.action == 'stop' and r.reason == 'no_positive_marginal_value'


def test_router_rejects_invalid_forecasts():
    with pytest.raises(ValidationError):
        f('consult_agent', 1, 0, .1)
    with pytest.raises(ValidationError):
        f('retrieve', float('nan'), 0, 0)
    with pytest.raises(ValueError):
        select_next_action([], remaining_api_budget_usd=-1, reservations_usd={})


def fixture():
    req = BrainstormRequest(session_id='adaptive', objective='Choose a general delivery path',
                             max_discussion_rounds=3, stop_after_no_new_rounds=3,
                             max_api_budget_usd=.05)
    a = ScriptedBrainstormAgent('a', Contribution(agent_id='a', new_ideas=[
        IdeaDraft(id='A',title='Fast',description='Fast route',expected_utility=60,
                  execution_cost=15,risk_loss=10,feasible=True)],
        position=Position(support_ids=['A']),reported_cost_usd=.002),
        discussions={1:Contribution(agent_id='a',new_ideas=[
            IdeaDraft(id='C',title='Hybrid',description='Combine approaches',parent_ids=['A','B'],
                expected_utility=85,execution_cost=10,risk_loss=8,feasible=True)],
                position=Position(support_ids=['C']),reported_cost_usd=.003),
                     3:Contribution(agent_id='a', position=Position(support_ids=['C']))},
        reserved_api_cost_usd=.01)
    b = ScriptedBrainstormAgent('b', Contribution(agent_id='b', new_ideas=[
        IdeaDraft(id='B',title='Robust',description='Safer approach',expected_utility=70,
                  execution_cost=25,risk_loss=7,feasible=True)],
        position=Position(support_ids=['B']),reported_cost_usd=.002),
        discussions={1:Contribution(agent_id='b',position=Position(oppose_ids=['C']))},
        reserved_api_cost_usd=.01)
    return req, [a,b]


def test_adaptive_routes_single_agent_preserves_dissent_and_new_idea():
    req, agents = fixture()
    r = asyncio.run(run_brainstorm(req, agents, adaptive_forecasts={
        1:[f('consult_agent', 8, 2, .01, 'a')],
        2:[f('discuss_all', 1, 2, .01)]}))
    assert r.stop_reason == 'information_not_worth_cost'
    assert [x.id for x in r.ideas] == ['A','B','C']
    assert r.traces[1].route_decision.action == 'consult_agent'
    assert r.traces[1].new_ids == ['C']
    assert r.selected_idea_id == 'C'


def test_adaptive_research_is_visible_in_following_round():
    req, agents = fixture()
    observed=[]
    async def research(view):
        return ResearchObservation(source_ref='https://example.org/report',summary='One project constraint',
                                   evidence_status='unverified',reported_cost_usd=.002)
    # inject an observer to see research notes in following discussion
    original=agents[0].discuss
    async def spy(view):
        observed.extend(view.research_observations)
        return await original(view)
    agents[0].discuss=spy
    r = asyncio.run(run_brainstorm(req, agents, adaptive_forecasts={
        1:[f('retrieve',5,1,.01)],2:[f('consult_agent',8,2,.01,'a')],
        3:[f('consult_agent',0,1,.01,'a')]},research_fn=research))
    assert [x.phase for x in r.traces] == ['independent','research','discussion']
    assert r.research_observations[0].summary == 'One project constraint'
    assert observed and observed[0].source_ref == 'https://example.org/report'
    assert r.reported_api_spent_usd == pytest.approx(.006)


def test_research_round_rejects_agent_contributions():
    req, _ = fixture()
    with pytest.raises(ValueError,match='Research round'):
        consolidate_brainstorm(req,[RoundTrace(round_number=0,phase='independent'),
            RoundTrace(round_number=1,phase='research', contributions=[Contribution(agent_id='x')])])


def test_adaptive_does_not_make_paid_calls_when_no_forecast():
    req, agents=fixture()
    r=asyncio.run(run_brainstorm(req, agents, adaptive_forecasts={}))
    assert len(r.traces)==1 and r.stop_reason=='information_not_worth_cost'


def test_router_reservations_override_underestimated_api_forecast():
    r=select_next_action([f('discuss_all',5,1,.001)],
          remaining_api_budget_usd=.03, reservations_usd={'a':.02,'b':.02})
    assert r.action=='stop' and r.ranked_actions[0].required_api_reservation_usd==pytest.approx(.04)


def test_invalid_agent_output_does_not_hide_spent_api_budget():
    req, agents=fixture()
    agents[1].independent.position = Position(support_ids=['future_unknown'])
    agents[1].independent.reported_cost_usd = .07
    r=asyncio.run(run_brainstorm(req,agents))
    assert r.reported_api_spent_usd == pytest.approx(.072)
    assert r.stop_reason == 'budget_exceeded'
    assert r.status == 'needs_estimates' or r.status == 'needs_review'


def test_research_cannot_start_as_first_round():
    req,_=fixture()
    with pytest.raises(ValueError,match='First trace'):
        consolidate_brainstorm(req,[RoundTrace(round_number=1,phase='research')])


def test_novelty_is_only_flagged_not_silently_merged():
    from pluralforge import surface_duplicate_flags
    drafts = [IdeaDraft(id='one',title='Staged rollout',description='Launch feature flags in phases'),
              IdeaDraft(id='two',title='Staged rollout',description='Launch feature flags in phases')]
    req=BrainstormRequest(session_id='dup',objective='compare')
    res=consolidate_brainstorm(req,[RoundTrace(round_number=0,phase='independent',contributions=[
        Contribution(agent_id='a',new_ideas=[drafts[0]]),
        Contribution(agent_id='b',new_ideas=[drafts[1]])])])
    assert len(res.ideas)==2
    assert res.novelty_flags[0].idea_id=='two'
    assert res.novelty_flags[0].resembles_id=='one'
    assert surface_duplicate_flags(res.ideas)
