"""Offline synthetic policy comparison under the SAME published budget cap.

This is a harness smoke test, NOT a claim of superior real-world LLM
performance. Synthetic true payoffs are kept separate from agent estimates.
"""
from __future__ import annotations
import asyncio
import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from arbiter_plugin import (
    BrainstormRequest, IdeaDraft, Contribution, Position,
    ScriptedBrainstormAgent, run_brainstorm, RoundTrace, consolidate_brainstorm,
)
from arbiter_plugin.adaptive import NextActionEstimate


@dataclass(frozen=True)
class Scenario:
    id: str
    domain: str
    objective: str
    estimated: dict[str, tuple[float, float, float]]
    true_payoffs: dict[str, float]  # synthetic held-out outcome label, never passed to agents
    api_budget_usd: float = .06


SCENARIOS = [
    Scenario('release', 'software', 'Plan release strategy',
             {'A': (78, 10, 14), 'B': (85, 25, 10), 'C': (90, 17, 8)},
             {'A': 45, 'B': 41, 'C': 55}),
    Scenario('experiment', 'research', 'Design a study',
             {'A': (84, 14, 10), 'B': (88, 29, 7), 'C': (83, 17, 8)},
             {'A': 54, 'B': 48, 'C': 51}),
    Scenario('supplier', 'procurement', 'Evaluate vendor options',
             {'A': (80, 10, 18), 'B': (86, 28, 7), 'C': (91, 19, 8)},
             {'A': 33, 'B': 46, 'C': 52}),
    Scenario('support', 'operations', 'Handle support overload',
             {'A': (74, 12, 11), 'B': (94, 37, 14), 'C': (84, 16, 9)},
             {'A': 42, 'B': 37, 'C': 43}),
    Scenario('workshop', 'planning', 'Organize a workshop',
             {'A': (77, 12, 8), 'B': (95, 32, 12), 'C': (89, 19, 9)},
             {'A': 52, 'B': 36, 'C': 50}),
]


def draft(s: Scenario, idea_id: str, parent_ids=None):
    u,c,r = s.estimated[idea_id]
    return IdeaDraft(id=idea_id,title=f'Alternative {idea_id}',
                     description=f'Synthetic {s.domain} plan {idea_id} with explicit assumptions',
                     parent_ids=parent_ids or [],expected_utility=u,
                     execution_cost=c,risk_loss=r,feasible=True)


def make_agents(s: Scenario):
    # 3 scripted agents; only the creative agent can propose C after seeing A+B.
    a = ScriptedBrainstormAgent('first',Contribution(agent_id='first',
        new_ideas=[draft(s,'A')],position=Position(support_ids=['A']),reported_cost_usd=.004),
        discussions={1:Contribution(agent_id='first', position=Position(support_ids=['A']),reported_cost_usd=.005)},
        reserved_api_cost_usd=.01)
    b = ScriptedBrainstormAgent('second',Contribution(agent_id='second',
        new_ideas=[draft(s,'B')],position=Position(support_ids=['B']),reported_cost_usd=.004),
        discussions={1:Contribution(agent_id='second', position=Position(support_ids=['B']),reported_cost_usd=.005)},
        reserved_api_cost_usd=.01)
    c = ScriptedBrainstormAgent('creative',Contribution(agent_id='creative',
        position=Position(note='Withhold synthesis until peers available'),reported_cost_usd=.004),
        discussions={1:Contribution(agent_id='creative', new_ideas=[draft(s,'C',['A','B'])],
            position=Position(support_ids=['C']),reported_cost_usd=.005)},
        reserved_api_cost_usd=.01)
    return [a,b,c]


def policies(s: Scenario):
    req = BrainstormRequest(session_id=s.id,objective=s.objective,
                            domain=s.domain,max_discussion_rounds=2,
                            max_api_budget_usd=s.api_budget_usd)
    agents = make_agents(s)
    # Both non-collaborative baselines use only the independent outputs.
    independent = [a.independent.model_copy(deep=True) for a in agents]
    single_trace=RoundTrace(round_number=0,phase='independent',contributions=[independent[0]])
    single=consolidate_brainstorm(req,[single_trace])
    vote_counts=Counter(i for c in independent for i in c.position.support_ids)
    vote=max(sorted(vote_counts),key=lambda i:vote_counts[i])
    # A majority voter with three distinct choices produces no true majority;
    # using deterministic tie-break is explicit and avoids faking consensus.
    vote_spend=sum(c.reported_cost_usd or 0 for c in independent)
    fixed=asyncio.run(run_brainstorm(req,make_agents(s)))
    forecast={
        1:[NextActionEstimate(action='consult_agent',agent_id='creative',
             expected_decision_gain=10,execution_cost_utility=3,
             estimated_api_cost_usd=.01,rationale='pre-registered synthetic host forecast'),
           NextActionEstimate(action='discuss_all',expected_decision_gain=9,
             execution_cost_utility=5,estimated_api_cost_usd=.03,
             rationale='pre-registered synthetic host forecast')],
        2:[NextActionEstimate(action='discuss_all', expected_decision_gain=1,
            execution_cost_utility=2, estimated_api_cost_usd=.03,
            rationale='pre-registered synthetic host forecast')],
    }
    adaptive=asyncio.run(run_brainstorm(req,make_agents(s),adaptive_forecasts=forecast))
    return {
        'single_agent':(single.selected_idea_id,single.reported_api_spent_usd,len(single.ideas)),
        'plurality_vote':(vote,vote_spend,len({d.id for c in independent for d in c.new_ideas})),
        'fixed_discussion':(fixed.selected_idea_id,fixed.reported_api_spent_usd,len(fixed.ideas)),
        'adaptive':(adaptive.selected_idea_id,adaptive.reported_api_spent_usd,len(adaptive.ideas)),
    }


def evaluate():
    rows=[]
    for s in SCENARIOS:
        ceiling=max(s.true_payoffs.values())
        for policy,(choice,api_cost,idea_count) in policies(s).items():
            if api_cost > s.api_budget_usd + 1e-9:
                raise AssertionError(f'{policy} exceeded scenario budget')
            payoff=s.true_payoffs.get(choice) if choice else None
            rows.append({'scenario':s.id, 'domain':s.domain, 'policy':policy,
                        'choice':choice, 'synthetic_realized_utility':payoff,
                        'synthetic_regret':(ceiling-payoff if payoff is not None else None),
                        'reported_api_cost_usd':round(api_cost,6),
                        'budget_cap_usd':s.api_budget_usd,'idea_count':idea_count})
    summary={}
    for policy in ('single_agent','plurality_vote','fixed_discussion','adaptive'):
        part=[r for r in rows if r['policy']==policy]
        summary[policy]={
            'tasks':len(part),
            'mean_synthetic_utility':round(sum(r['synthetic_realized_utility'] for r in part)/len(part),3),
            'mean_synthetic_regret':round(sum(r['synthetic_regret'] for r in part)/len(part),3),
            'mean_reported_api_usd':round(sum(r['reported_api_cost_usd'] for r in part)/len(part),5),
            'mean_candidates':round(sum(r['idea_count'] for r in part)/len(part),2),
        }
    return {'disclaimer':'Scripted synthetic fixtures only; no LLM superiority demonstrated. No real API called.',
            'equal_budget_caps':True,'cases':len(SCENARIOS),'summary':summary,'rows':rows}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='benchmarks/offline_comparison.json')
    args=parser.parse_args()
    report=evaluate()
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('SYNTHETIC benchmark, NOT real LLM performance')
    for name,metrics in report['summary'].items():
        print(f'{name:18} mean utility={metrics["mean_synthetic_utility"]:5.1f}  '
              f'regret={metrics["mean_synthetic_regret"]:5.1f}  '
              f'API=${metrics["mean_reported_api_usd"]:.4f}  ideas={metrics["mean_candidates"]}')
    print(f'Full result: {args.output}')


if __name__=='__main__':
    main()
