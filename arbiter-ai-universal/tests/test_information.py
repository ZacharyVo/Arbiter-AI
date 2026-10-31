from arbiter_plugin import ResearchRequest, ResearchOption, plan_information

def test_positive_evsi():
    out=plan_information(ResearchRequest(decision_id='x',max_api_budget_usd=.1,
        opportunities=[ResearchOption(id='search',expected_information_gain=10,research_cost_utility=2,estimated_api_cost_usd=.02)]))
    assert out.action == 'research' and out.recommended_research_id == 'search'

def test_negative_evsi_stops():
    out=plan_information(ResearchRequest(decision_id='x',max_api_budget_usd=.1,
        opportunities=[ResearchOption(id='bad',expected_information_gain=1,research_cost_utility=2)]))
    assert out.action=='decide_now'

def test_budget_exceeded():
    out=plan_information(ResearchRequest(decision_id='x',max_api_budget_usd=.03,api_spent_usd=.04,
        opportunities=[ResearchOption(id='search',expected_information_gain=10,research_cost_utility=0)]))
    assert out.action=='decide_now'

def test_budget_insufficient():
    out=plan_information(ResearchRequest(decision_id='x',max_api_budget_usd=.02,
        opportunities=[ResearchOption(id='search',expected_information_gain=10,research_cost_utility=0,
                                       estimated_api_cost_usd=.03)]))
    assert out.action=='decide_now'

def test_requires_approval():
    out=plan_information(ResearchRequest(decision_id='x',max_api_budget_usd=.10,
        opportunities=[ResearchOption(id='search',expected_information_gain=10,research_cost_utility=0,
                                       requires_approval=True)]))
    assert out.action=='needs_review'

def test_selects_best_net_value():
    out=plan_information(ResearchRequest(decision_id='x',max_api_budget_usd=.10,opportunities=[
        ResearchOption(id='first',expected_information_gain=4,research_cost_utility=1),
        ResearchOption(id='second',expected_information_gain=8,research_cost_utility=2)]))
    assert out.recommended_research_id == 'second'
