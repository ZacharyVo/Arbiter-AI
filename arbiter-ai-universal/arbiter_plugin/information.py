"""Economically meaningful information-gathering recommendations, not automatic calls."""
from .models import ResearchRequest, ResearchRecommendation


def plan_information(request: ResearchRequest) -> ResearchRecommendation:
    remaining = request.max_api_budget_usd - request.api_spent_usd
    notes: list[str] = []
    if remaining < 0:
        notes.append('API budget already exceeded; do not authorize further paid calls')
        return ResearchRecommendation(decision_id=request.decision_id, action='decide_now', notes=notes)

    eligible = [x for x in request.opportunities
                if x.expected_information_gain > x.research_cost_utility
                and x.estimated_api_cost_usd <= remaining]
    if not eligible:
        notes.append('No positive net information-value option within remaining estimated budget')
        return ResearchRecommendation(decision_id=request.decision_id, action='decide_now', notes=notes)
    chosen = sorted(eligible, key=lambda x: (-(x.expected_information_gain-x.research_cost_utility),
                                           x.estimated_api_cost_usd, x.id))[0]
    notes.append('EVSI estimates are user supplied, not derived from disagreement entropy')
    notes.append('API budget is preflight estimate; provider-side limits are needed for hard caps')
    return ResearchRecommendation(decision_id=request.decision_id,
        action='needs_review' if chosen.requires_approval else 'research',
        recommended_research_id=chosen.id,
        expected_net_information_value=chosen.expected_information_gain-chosen.research_cost_utility,
        notes=notes)
