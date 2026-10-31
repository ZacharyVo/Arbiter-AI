import pytest
from pydantic import ValidationError
from arbiter_plugin import Option, Opinion, DecisionRequest, evaluate_decision, disagreement_entropy


def r(**k):
    defaults = dict(decision_id='case', objective='Choose', options=[
        Option(id='a', expected_utility=80, execution_cost=10, risk_loss=10),
        Option(id='b', expected_utility=65, execution_cost=0, risk_loss=0)])
    defaults.update(k)
    return DecisionRequest(**defaults)


def test_utility_selection():
    out = evaluate_decision(r())
    assert out.selected_option_id == 'b'  # a=60, b=65
    assert out.status == 'proposed'


def test_cost_update_changes_decision():
    req = r()
    assert evaluate_decision(req).selected_option_id == 'b'
    req.options[0].execution_cost = 0
    assert evaluate_decision(req).selected_option_id == 'a'


def test_hard_risk_threshold():
    out = evaluate_decision(r(maximum_risk_loss=1))
    assert out.selected_option_id == 'b'
    assert out.scores[1].feasible is False


def test_all_infeasible():
    req = r(maximum_risk_loss=0)
    req.options[1].feasible = False
    assert evaluate_decision(req).status == 'no_feasible_option'


def test_risk_flag_reviews():
    out = evaluate_decision(r(opinions=[Opinion(agent_id='x', option_id='b', risk_flag=True)]))
    assert out.status == 'needs_review'


def test_human_review_request():
    assert evaluate_decision(r(require_human_review=True)).status == 'needs_review'


def test_consensus_weighted_reputation():
    req = r(mode='consensus', opinions=[Opinion(agent_id='a1', option_id='a'),
                                             Opinion(agent_id='a2', option_id='b')])
    assert evaluate_decision(req, {'a1': .2, 'a2': .9}).selected_option_id == 'b'


def test_self_report_confidence_does_not_change_vote():
    req = r(mode='consensus', opinions=[Opinion(agent_id='x', option_id='a', confidence=1,
                                                  confidence_source='self_report'),
                                            Opinion(agent_id='y', option_id='b', confidence=0.01,
                                                  confidence_source='self_report')])
    result = evaluate_decision(req, {'x': .4, 'y': .7})
    assert result.selected_option_id == 'b'
    assert 'Self-reported confidence' in '\n'.join(result.notes)


def test_calibrated_confidence_can_change_vote():
    req = r(mode='consensus', opinions=[Opinion(agent_id='x', option_id='a', confidence=.2,
                                                  confidence_source='calibrated'),
                                            Opinion(agent_id='y', option_id='b', confidence=.9,
                                                  confidence_source='calibrated')])
    assert evaluate_decision(req, {'x': .9, 'y': .5}).selected_option_id == 'b'


def test_disagreement_and_abstention():
    req = r(opinions=[Opinion(agent_id='x', option_id='a'),Opinion(agent_id='y',option_id='b'),
                      Opinion(agent_id='z', option_id=None)])
    assert disagreement_entropy(req) == 1.0


def test_agreement_zero_entropy():
    req = r(opinions=[Opinion(agent_id='x', option_id='a'),Opinion(agent_id='y',option_id='a')])
    assert disagreement_entropy(req) == 0


def test_no_vote_entropy_zero():
    assert disagreement_entropy(r()) == 0


def test_validates_unknown_option():
    with pytest.raises(ValidationError):
        r(opinions=[Opinion(agent_id='x', option_id='missing')])


def test_validates_duplicate_agents():
    with pytest.raises(ValidationError):
        r(opinions=[Opinion(agent_id='x', option_id='a'),Opinion(agent_id='x', option_id='b')])


def test_validates_duplicate_options():
    with pytest.raises(ValidationError):
        r(options=[Option(id='a', expected_utility=1),Option(id='a', expected_utility=2)])


def test_rubric_mode():
    req = DecisionRequest(decision_id='rubric', objective='Compare providers',
        criterion_weights={'quality':2,'speed':1},
        options=[Option(id='x',criterion_scores={'quality':90,'speed':30},execution_cost=10),
                 Option(id='y',criterion_scores={'quality':60,'speed':90},execution_cost=0)])
    out = evaluate_decision(req)
    assert out.selected_option_id == 'y'
    assert out.scores[1].base_utility == 70


def test_missing_rubric_rejected():
    with pytest.raises(ValidationError):
        DecisionRequest(decision_id='x',objective='x',criterion_weights={'a':1},
                        options=[Option(id='one',criterion_scores={'b':20})])


def test_invalid_rubric_range():
    with pytest.raises(ValidationError):
        Option(id='x',criterion_scores={'quality':120})


def test_consensus_allows_no_utility():
    out = evaluate_decision(DecisionRequest(decision_id='x',objective='x',mode='consensus',
          options=[Option(id='a'),Option(id='b')], opinions=[Opinion(agent_id='x',option_id='b')]))
    assert out.selected_option_id == 'b'


def test_custom_domain_hooks():
    req = r()
    out = evaluate_decision(req, utility_fn=lambda ctx, option: 100 if option.id == 'a' else 30,
                            feasibility_fn=lambda ctx, option: option.id != 'a')
    assert out.selected_option_id == 'b'  # custom hard policy trumps utility


def test_non_finite_utility_rejected():
    with pytest.raises(ValueError):
        evaluate_decision(r(), utility_fn=lambda ctx, option: float('inf'))
