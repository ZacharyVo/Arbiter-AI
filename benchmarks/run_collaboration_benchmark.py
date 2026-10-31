"""Synthetic regression checks; NOT evidence of real LLM superiority."""
import asyncio
from examples.collaborative_demo import create_demo
from arbiter_plugin import BrainstormRequest, IdeaDraft, Contribution, RoundTrace, consolidate_brainstorm, run_brainstorm


def main():
    req, agents = create_demo()
    got = asyncio.run(run_brainstorm(req, agents))
    checks = {
      'creates_new_idea_from_prior_candidates': any(i.id == 'hybrid' and i.parent_ids == ['fast', 'complete'] for i in got.ideas),
      'maintains_nonconsensus': len(got.dissents) == 3,
      'stops_when_marginal_value_is_negative': got.stop_reason == 'information_not_worth_cost',
      'risk_warning_needs_review': got.status == 'needs_review',
      'no_unverified_numeric_guessing': consolidate_brainstorm(
          BrainstormRequest(session_id='missing', objective='Explore'),
          [RoundTrace(round_number=0, phase='independent', contributions=[
             Contribution(agent_id='x', new_ideas=[IdeaDraft(id='open', title='Open proposal', description='Unpriced')])])]
         ).status == 'needs_estimates',
    }
    for k, passed in checks.items():
        print(f'{"PASS" if passed else "FAIL"}: {k}')
    print(f'{sum(checks.values())}/{len(checks)} synthetic contract checks')
    if not all(checks.values()):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
