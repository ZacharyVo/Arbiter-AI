# PluralForge AI

**Many minds. New ideas. Better decisions.**  
**Cost-aware collective intelligence & decision optimization.**

![Offline interactive demo](docs/preview.png)

> **PluralForge** is an open-source, domain-neutral Python decision layer for multi-agent systems. Agents may independently propose ideas, challenge each other, synthesize **new options**, and **keep disagreeing**. An auditable utility scorer and a budget-aware next-step router decide what the *software recommends*, not an all-powerful meta-judge. It **never executes real-world actions**.

**中文简介：** 通用多 Agent 协作决策插件：独立思考 → 交叉质疑 → 产生新方案 → 保留分歧 → 动态选择下一次讨论、检索或停止 → 可解释评分 → 独立验证。目标不是让 AI 达成共识，而是在预算、风险、不确定性约束下提升决策质量。

**Status:** v0.5 research MVP · Python 3.11+ · MIT · offline-first. Optional integrations: LiteLLM, local REST API, MCP. The public `pluralforge` import path is new; `arbiter_plugin` imports are retained for compatibility.

## Why this exists

More model calls and longer debates do **not** necessarily produce better answers. PluralForge treats deliberation as an **investment decision**: compare the *expected improvement* of each available next step against its cost, while respecting the remaining API budget. It does **not** force consensus or presume the extra calls will help.

### What is in v0.5

| Component | What it actually does | Important boundary |
|---|---|---|
| Independent brainstorming | Async agents propose separately before reading peers | External model calls require explicit setup |
| Collaborative proposals | Agents critique, revise, combine and introduce new idea IDs with provenance | IDs alone do not establish semantic novelty |
| Preserve dissent | Store support, opposition, and full discussion traces | Consensus is not a success metric |
| Adaptive action routing | Select `consult_agent`, `discuss_all`, `retrieve`, or `stop` by estimated **net information value** and reservations | Forecast inputs can be host supplied or estimated from sparse, verified historical observations; causal effects remain unproven |
| Novelty hints | Surface-form similarity warnings, no forced merging | Not semantic embedding-based deduplication |
| Decision scoring | `expected_utility - execution_cost - risk_aversion * risk_loss` | Missing estimates block final selection; all in the same utility unit |
| Audit and feedback | SQLite host-attested outcome records and provenance | Evidence must be externally verified; no auto-retraining |
| **Information Value Learning Engine (v0.5)** | Learns regularized per-action marginal gain and costs from evidence-attributed historical outcomes, with time-cutoff checks and abstention | Observational predictor only; **not causal VoI**, no learned hard spend cap |
| Policy comparison | Scripted cross-domain cases comparing single agent, voting, fixed discussion and adaptive routing | Synthetic illustrations **are not real LLM benchmark results** |
| Interfaces | Python SDK, optional local HTTP and MCP tools | MCP handshake and paid model integrations require environment-specific testing |

## Installation

```powershell
# Windows / VS Code, from repository root
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

python -m examples.adaptive_demo
python -m examples.value_learning_demo
python -m benchmarks.learning_temporal_replay
python -m examples.collaborative_demo
python -m benchmarks.compare_policies
python -m pytest
```

For Linux/macOS use `python3 -m venv .venv && source .venv/bin/activate`. None of the commands above make paid model calls.

### GitHub Pages demonstration

Open [`docs/index.html`](docs/index.html) directly in a browser, or publish `/docs` through **Settings → Pages**. The offline webpage illustrates discussion rounds, disagreement, utility scoring and routing; it does not call a remote model.

## One function: should we keep thinking?

```python
from pluralforge import NextActionEstimate, select_next_action

candidates = [
    NextActionEstimate(
        action="consult_agent", agent_id="critic",
        expected_decision_gain=8, execution_cost_utility=2,
        estimated_api_cost_usd=0.02,
        rationale="Host estimates a targeted critique may reveal failure modes",
    ),
    NextActionEstimate(
        action="discuss_all",
        expected_decision_gain=7, execution_cost_utility=5,
        estimated_api_cost_usd=0.08,
        rationale="Full second discussion round",
    ),
]

plan = select_next_action(
    candidates,
    remaining_api_budget_usd=0.05,
    reservations_usd={"critic": 0.02, "builder": 0.03},
)
print(plan.action, plan.agent_id)  # consult_agent critic
```

`expected_decision_gain` and `execution_cost_utility` are in **the same decision utility unit** (e.g., calibrated points). API costs and reservations are measured separately in **USD**; the router does not subtract USD directly from abstract points. The `rationale` should record the origin of the forecast. The router filters unaffordable and unavailable actions and chooses the highest positive net value. If no action qualifies, it recommends `stop`.

**The deterministic router accepts explicit host forecasts, and v0.5 can also supply empirical forecasts from earlier host-verified observations.** These observational estimates are not proven causal value of information. Forecast calibration remains an open research challenge. Preflight spending reservations cannot enforce provider billing limits.

## Information Value Learning Engine · NEW v0.5

When the host supplies verified feedback, PluralForge can learn which consultation, extra discussion or retrieval action **historically improved a comparable decision-quality rubric** in the same domain and context. It keeps execution cost (utility points) separate from API spend (USD), requires a minimum amount of past feedback, and **abstains** without sufficient evidence or an explicitly declared host prior.

```python
from datetime import datetime, timezone
from pluralforge import (LearningContext, ActionCandidate, LearningRequest,
                         InformationValueLearner)

learner = InformationValueLearner('local_value_feedback.sqlite')
request = LearningRequest(
    context=LearningContext(domain='software', utility_unit='points',
                            tags={'task': 'architecture'}),
    candidates=[ActionCandidate(action='consult_agent', agent_id='critic'),
                ActionCandidate(action='retrieve')],
    as_of=datetime.now(timezone.utc),
)
report = learner.forecast(request)
print([(r.action, r.source) for r in report.forecasts])
# New databases return insufficient_data; they DO NOT invent forecasts.
```

A verified observation records before/after scores, execution cost, API cost, event time, evidence-availability time, independent verifier identifier and evidence reference. Recording requires `confirm_verified=True`. See [the full learning design](docs/INFORMATION_VALUE_LEARNING.md) and `examples/value_learning_demo.py` for end-to-end synthetic examples.

`run_brainstorm` also accepts `value_learner=learner` plus `learning_tags` and `learning_as_of`; for discussion rounds, the learner supplies only supported historical forecasts. If none is supported, the system recommends stopping additional API calls. Explicit host-provided adaptive forecasts take priority.

**Research caveat:** this is a conservative historical estimator, *not* proof of a causal improvement or an actual learned neural policy. The temporal replay evaluates the accuracy of forecasts on **logged actions**, not counterfactual action choices. More calls may still make an answer worse.

## Full collaborative decision workflow

The SDK can orchestrate real agents with `propose()` and `discuss()` methods (see [`arbiter_plugin/brainstorm_agents.py`](arbiter_plugin/brainstorm_agents.py)). Or it can process a transcript generated by any external host without calling an LLM.

```python
import asyncio
from examples.collaborative_demo import create_demo
from pluralforge import NextActionEstimate, run_brainstorm

req, agents = create_demo()  # scripted fixture; no live LLM
forecast = {
    1: [NextActionEstimate(action="consult_agent", agent_id="creative",
         expected_decision_gain=9, execution_cost_utility=2,
         estimated_api_cost_usd=0.02, rationale="Host forecast")],
    2: [NextActionEstimate(action="consult_agent", agent_id="quality",
         expected_decision_gain=5, execution_cost_utility=1,
         estimated_api_cost_usd=0.02, rationale="Host forecast")],
    3: [NextActionEstimate(action="discuss_all",
         expected_decision_gain=1, execution_cost_utility=3,
         estimated_api_cost_usd=0.06, rationale="Marginal gain too small")],
}
result = asyncio.run(run_brainstorm(req, agents, adaptive_forecasts=forecast))
print(result.provisional_leader_id, result.status, result.stop_reason)
print([(d.idea_id, d.supporters, d.opponents) for d in result.dissents])
```

The orchestrator first gathers **independent** proposals. In later rounds it follows the recommended action and preserves all contributions and route decisions. New ideas have `parent_ids`. Unknown utility/cost/risk/feasibility fields lead to `needs_estimates`, never invented values. Risk warnings trigger review. Nothing automatically performs a consequential action.

### Optional retrieval action

When a `retrieve` action has the best forecast, provide an async `research_fn(view)` returning a `ResearchObservation(source_ref=..., summary=..., evidence_status="unverified")`. The observation becomes part of the auditable shared view in later rounds. External sources do **not** become verified facts merely by retrieval. See `tests/test_adaptive.py` for an executable example.

## Benchmarks and scientific claims

```powershell
python -m benchmarks.compare_policies
# results saved in benchmarks/offline_comparison.json
```

`python -m benchmarks.learning_temporal_replay` additionally evaluates the new predictor on sequential **synthetic, logged-action** samples. It does not make counterfactual policy improvement claims.

The cross-domain fixture runner compares **single agent**, **plurality vote**, **fixed discussion** and **adaptive** under the **same maximum API budget per case** (not necessarily identical actual expenditure). It reports candidate count, assumed realized utility, regret, and reported API cost. The 5 cases use *hand-authored simulated agents and outcomes*. They test the evaluation plumbing and show how to record counterfactual policies; they **cannot demonstrate true superiority** of this architecture over any LLM or baseline.

See [`docs/BENCHMARK_PROTOCOL.md`](docs/BENCHMARK_PROTOCOL.md) for the proposed real-world evaluation: human/external ground truth, held-out tasks, matched budget caps and optionally matched spend, blinded judging, calibration, latency, safety, repeated runs, confidence intervals and an ablation on the routing/brainstorming stages.

## Integrations

**Python SDK:** import from `pluralforge` (preferred), or `arbiter_plugin` (backwards compatible).

**Local HTTP API:**

```powershell
python -m pip install -e ".[api]"
python -m uvicorn arbiter_plugin.api:app --host 127.0.0.1 --port 8000
```

`POST /v1/next-step` accepts forecasts, budget and reservations, returning the selected next step and alternative rankings. `POST /v1/brainstorm` consolidates host-provided discussion traces only; it does not spawn any model. The new `/v1/value/record`, `/v1/value/forecast`, and `/v1/value/next-step` endpoints expose local learning storage, forecasts and budget-aware routing. Other existing endpoints cover deterministic scoring and research planning. `GET /docs` shows the OpenAPI docs.

**MCP (optional):**

```powershell
python -m pip install -e ".[mcp]"
python -m arbiter_plugin.mcp_server
```

The adapter adds `pluralforge_value_forecast`, `pluralforge_value_next_step`, and `pluralforge_record_value_feedback` alongside `pluralforge_plan_next_step` and legacy `arbiter_brainstorm`, `arbiter_evaluate`, `arbiter_plan_research`, `arbiter_record_verified_outcome` tools. SDK compatibility is environment-dependent; **no live host handshake is claimed**.

**Paid multi-model brainstorming (optional):**

```powershell
python -m pip install -e ".[llm]"
# Set provider-specific API keys using your own local environment
python -m examples.live_brainstorm
```

The LiteLLM adapter is opt-in and has not been verified against live providers in this package. Never commit real API secrets, local `.env` files, or private research data. The example HTTP server has **no authentication**—do not expose it to the public Internet without authentication, TLS, rate limits, isolation, and authorization.

## Project layout

```text
pluralforge-ai-v0.5/
├── pluralforge/               # Preferred public Python imports
├── arbiter_plugin/            # Backward-compatible engine
│   ├── adaptive.py            # Cost-aware next-action router
│   ├── value_learning.py      # NEW: as-of verified feedback learning
│   ├── collaboration.py       # New proposals, dissent, orchestration and scoring
│   ├── novelty.py             # Non-destructive duplicate wording flags
│   ├── brainstorm_agents.py   # Scripted agents and optional LiteLLM adapter
│   ├── core.py, models.py     # Deterministic decision evaluation contracts
│   ├── information.py        # Explicit research-value calculator
│   ├── feedback.py           # SQLite verified outcomes
│   ├── api.py, mcp_server.py  # Optional host interfaces
│   └── benchmark.py          # Core regression scoring
├── examples/                  # Offline + optional real-API demos
├── benchmarks/                # Synthetic baselines + chronological learning replay
├── tests/                     # Automatic unit/regression tests
├── docs/                      # Architecture, benchmark protocol, static demo
├── .github/workflows/tests.yml
├── pyproject.toml
└── LICENSE
```

## Non-goals and limitations

- **No forced consensus, no all-powerful meta-judge, no automatic execution.** Agent agreement is not equivalent to truth.
- **No proven causal value-of-information estimator:** observed historical gains are selectively logged and may be biased. Cold starts abstain; host priors must be explicit. Temporal replay is necessary but insufficient.
- **No verified semantic novelty model:** similarity hints are surface-text comparisons only; candidates are never silently merged.
- **Not production security or a hosted commercial plugin.** MCP and HTTP hosting need additional authentication and operational controls.
- **Not a validated real-world benchmark of AI intelligence.** The automated tests and offline fixture results demonstrate software behavior, not model quality.

## Roadmap

- [x] Independent initial proposals, new idea lineage, dissent-preserving traces
- [x] Transparent utility/risk/cost scoring with unknown-value gates
- [x] Explicit next-step routing between one agent, all agents, retrieval, and stop
- [x] Local HTTP route API and optional MCP entry point
- [x] Synthetic cross-domain policy comparison and novelty warnings
- [ ] Independently labeled real-task benchmarks with cost controls and repeated runs
- [x] Host-attested information-value history, regularized empirical forecasts and chronological synthetic replay
- [ ] Causal/counterfactual information-value learning validated on independent real task data
- [ ] Pluggable semantic equivalence and evidence-checking evaluators
- [ ] Provider-specific hard spend caps, robust rate limiting, authentication, and audited deployments

**License:** MIT. See [LICENSE](LICENSE). Contributions are welcome with reproducible tests, clear failure cases and explicit source boundaries.
