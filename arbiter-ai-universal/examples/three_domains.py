"""Offline cross-domain examples. No external LLM or provider account required."""
from arbiter_plugin import DecisionRequest, Option, Opinion, evaluate_decision

scenarios = [
    DecisionRequest(decision_id='engineering-001', objective='Select a release strategy', domain='software',
        utility_unit='points', options=[
            Option(id='ship_mvp', expected_utility=83, execution_cost=12, risk_loss=8),
            Option(id='rebuild', expected_utility=94, execution_cost=39, risk_loss=18)],
        opinions=[Opinion(agent_id='reviewer_a', option_id='ship_mvp', rationale='Faster iteration'),
                  Opinion(agent_id='reviewer_b', option_id='rebuild', confidence=.92, confidence_source='self_report')]),
    DecisionRequest(decision_id='planning-002', objective='Choose a study plan', domain='education',
        utility_unit='points', criterion_weights={'learning': .65, 'flexibility': .35},
        options=[Option(id='guided', criterion_scores={'learning': 90, 'flexibility': 60}, execution_cost=8, risk_loss=2),
                 Option(id='self_study', criterion_scores={'learning': 75, 'flexibility': 95}, execution_cost=4, risk_loss=5)]),
    DecisionRequest(decision_id='research-003', objective='Choose the next experiment', domain='research',
        mode='consensus', options=[Option(id='experiment_a'),Option(id='experiment_b')],
        opinions=[Opinion(agent_id='scientist_a', option_id='experiment_a'),
                  Opinion(agent_id='scientist_b', option_id='experiment_a'),
                  Opinion(agent_id='scientist_c', option_id='experiment_b')])
]

if __name__ == '__main__':
    for req in scenarios:
        result = evaluate_decision(req)
        print(f'{req.domain}: {result.selected_option_id} [{result.status}]')
        for score in result.scores:
            print(f'  {score.option_id:14s} net={score.net_utility:6.1f} votes={score.votes:.2f}')
