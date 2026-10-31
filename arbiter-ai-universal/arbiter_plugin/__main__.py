"""Quick offline demonstration: python -m arbiter_plugin"""
from .models import DecisionRequest, Option, Opinion
from .core import evaluate_decision

if __name__ == '__main__':
    request = DecisionRequest(decision_id='example-1',objective='Which implementation should we ship?',domain='software',
        options=[Option(id='simple',expected_utility=75,execution_cost=10,risk_loss=5),
                 Option(id='advanced',expected_utility=95,execution_cost=35,risk_loss=20)],
        opinions=[Opinion(agent_id='reviewer-a',option_id='simple',rationale='Easier to maintain'),
                  Opinion(agent_id='reviewer-b',option_id='advanced',rationale='More features')])
    print(evaluate_decision(request).model_dump_json(indent=2))
