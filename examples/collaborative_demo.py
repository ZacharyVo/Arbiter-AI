"""Offline end-to-end collaborative brainstorming: independent -> challenge -> novel idea -> dissent."""
from __future__ import annotations
import asyncio
from arbiter_plugin import (
    BrainstormRequest, IdeaDraft, Contribution, CritiqueDraft, Position,
    InformationEstimate, ScriptedBrainstormAgent, run_brainstorm,
)


def create_demo():
    req = BrainstormRequest(
        session_id='release-workflow',
        objective='Choose a sustainable way to deliver a new software feature',
        domain='software', utility_unit='points', max_discussion_rounds=3,
        max_api_budget_usd=0.20, stop_after_no_new_rounds=2,
        round_information_estimates={
            1: InformationEstimate(expected_decision_gain=15, discussion_cost_utility=3),
            2: InformationEstimate(expected_decision_gain=6, discussion_cost_utility=2),
            3: InformationEstimate(expected_decision_gain=2, discussion_cost_utility=4),
        },
    )
    speed = ScriptedBrainstormAgent(
        agent_id='speed',
        independent=Contribution(agent_id='speed', new_ideas=[IdeaDraft(
            id='fast', title='Ship an MVP', description='Short pilot with explicit scope',
            expected_utility=82, execution_cost=12, risk_loss=12, feasible=True,
            open_questions=['Is the MVP support burden acceptable?'])],
            position=Position(support_ids=['fast'], note='Optimize speed')),
        discussions={1: Contribution(agent_id='speed',
            critiques=[CritiqueDraft(target_id='complete', claim='Long lead time delays feedback', severity='challenge')],
            position=Position(support_ids=['fast'], oppose_ids=['complete'], note='Still prefer fast release')),
            2: Contribution(agent_id='speed', position=Position(support_ids=['fast', 'hybrid'], oppose_ids=['complete'], note='Hybrid may be feasible')),
            },
    )
    quality = ScriptedBrainstormAgent(
        agent_id='quality',
        independent=Contribution(agent_id='quality', new_ideas=[IdeaDraft(
            id='complete', title='Build full architecture first', description='Full functionality before launch',
            expected_utility=96, execution_cost=46, risk_loss=20, feasible=True)],
            position=Position(support_ids=['complete'], note='Reliability first')),
        discussions={1: Contribution(agent_id='quality',
            critiques=[CritiqueDraft(target_id='fast', claim='Untested migrations may fail', severity='risk_warning')],
            position=Position(support_ids=['complete'], oppose_ids=['fast'])),
            2: Contribution(agent_id='quality',
                critiques=[CritiqueDraft(target_id='hybrid', claim='Feature flags require rollback owners', severity='challenge')],
                position=Position(support_ids=['complete'], oppose_ids=['fast', 'hybrid'])),
            },
    )
    creative = ScriptedBrainstormAgent(
        agent_id='creative',
        independent=Contribution(agent_id='creative',
            position=Position(note='Need to inspect both approaches before proposing a synthesis')),
        discussions={1: Contribution(agent_id='creative', new_ideas=[IdeaDraft(
            id='hybrid', title='Staged rollout with feature flags',
            description='Small pilot + automated gates and rollback', parent_ids=['fast', 'complete'],
            expected_utility=93, execution_cost=20, risk_loss=8, feasible=True,
            open_questions=['Who owns rollback checks?'])],
            position=Position(support_ids=['hybrid'], oppose_ids=['complete'])),
            2: Contribution(agent_id='creative', position=Position(support_ids=['hybrid'], oppose_ids=['complete'])),
            },
    )
    return req, [speed, quality, creative]


async def main():
    req, agents = create_demo()
    result = await run_brainstorm(req, agents)
    print('STOP:', result.stop_reason)
    print('STATUS:', result.status)
    print('SELECTED:', result.selected_idea_id)
    print('NEW IDEAS:', [(x.id, x.created_by, x.parent_ids) for x in result.ideas])
    print('PERSISTING DISSENT:', [x.model_dump() for x in result.dissents])
    print('RANKING:', [(x.idea_id, x.net_utility) for x in result.scores])
    print('TRACES:', [(x.round_number, x.phase, x.new_ids) for x in result.traces])
    print('NOTES:', result.notes)


if __name__ == '__main__':
    asyncio.run(main())
