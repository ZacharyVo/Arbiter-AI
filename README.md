# PluralForge AI

**Many minds. New ideas. Better decisions.**  
**Cost-aware collective intelligence & decision optimization.**

![Offline interactive demo](docs/preview.png)

> **PluralForge** is an open-source, domain-neutral Python decision layer for multi-agent systems. Agents may independently propose ideas, challenge each other, synthesize **new options**, and **keep disagreeing**. An auditable utility scorer and a budget-aware next-step router decide what the *software recommends*, not an all-powerful meta-judge. It **never executes real-world actions**.

**中文简介：** 通用多 Agent 协作决策插件：独立思考 → 交叉质疑 → 产生新方案 → 保留分歧 → 动态选择下一次讨论、检索或停止 → 可解释评分 → 独立验证。目标不是让 AI 达成共识，而是在预算、风险、不确定性约束下提升决策质量。

**Status:** v0.4 research MVP · Python 3.11+ · MIT · offline-first. Optional integrations: LiteLLM, local REST API, MCP. The public `pluralforge` import path is new; `arbiter_plugin` imports are retained for compatibility.

## Why this exists

More model calls and longer debates do **not** necessarily produce better answers. PluralForge treats deliberation as an **investment decision**: compare the *expected improvement* of each available next step against its cost, while respecting the remaining API budget. It does **not** force consensus or presume the extra calls will help.

### What is in v0.4

| Component | What it actually does | Important boundary |
|---|---|---|
| Independent brainstorming | Async agents propose separately before reading peers | External model calls require explicit setup |
| Collaborative proposals | Agents critique, revise, combine and introduce new idea IDs with provenance | IDs alone do not establish semantic novelty |
| Preserve dissent | Store support, opposition, and full discussion traces | Consensus is not a success metric |
| Adaptive action routing **NEW** | Select `consult_agent`, `discuss_all`, `retrieve`, or `stop` by estimated **net information value** and reservations | Expected gains/costs are **external forecasts**, not automatically calibrated |
| Novelty hints **NEW** | Surface-form similarity warnings, no forced merging | Not semantic embedding-based deduplication |
| Decision scoring | `expected_utility - execution_cost - risk_aversion * risk_loss` | Missing estimates block final selection; all in the same utility unit |
| Audit and feedback | SQLite verified-outcome records and clear source distinctions | No online reinforcement learning or auto-retraining yet |
| Policy comparison **NEW** | Scripted cross-domain cases comparing single agent, voting, fixed discussion and adaptive routing | Synthetic illustrations **are not real LLM benchmark results** |
| Interfaces | Python SDK, optional local HTTP and MCP tools | MCP handshake and paid model integrations require environment-specific testing |

## Installation

```powershell
# Windows / VS Code, from repository root
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

python -m examples.adaptive_demo
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

**This is a transparent planning heuristic using supplied VoI estimates, not a learned VoI model.** Forecast quality is an explicit unsolved research and evaluation problem. Preflight spending reservations cannot enforce provider billing limits.

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

The cross-domain fixture runner compares **single agent**, **plurality vote**, **fixed discussion** and **adaptive** under the **same maximum API budget per case** (not necessarily identical actual expenditure). It reports candidate count, assumed realized utility, regret, and reported API cost. The 5 cases use *hand-authored simulated agents and outcomes*. They test the evaluation plumbing and show how to record counterfactual policies; they **cannot demonstrate true superiority** of this architecture over any LLM or baseline.

See [`docs/BENCHMARK_PROTOCOL.md`](docs/BENCHMARK_PROTOCOL.md) for the proposed real-world evaluation: human/external ground truth, held-out tasks, matched budget caps and optionally matched spend, blinded judging, calibration, latency, safety, repeated runs, confidence intervals and an ablation on the routing/brainstorming stages.

## Integrations

**Python SDK:** import from `pluralforge` (preferred), or `arbiter_plugin` (backwards compatible).

**Local HTTP API:**

```powershell
python -m pip install -e ".[api]"
python -m uvicorn arbiter_plugin.api:app --host 127.0.0.1 --port 8000
```

`POST /v1/next-step` accepts forecasts, budget and reservations, returning the selected next step and alternative rankings. `POST /v1/brainstorm` consolidates host-provided discussion traces only; it does not spawn any model. Other existing endpoints cover deterministic scoring and research planning. `GET /docs` shows the OpenAPI docs.

**MCP (optional):**

```powershell
python -m pip install -e ".[mcp]"
python -m arbiter_plugin.mcp_server
```

The adapter includes `pluralforge_plan_next_step` and legacy `arbiter_brainstorm`, `arbiter_evaluate`, `arbiter_plan_research`, `arbiter_record_verified_outcome` tools. SDK compatibility is environment-dependent; **no live host handshake is claimed**.

**Paid multi-model brainstorming (optional):**

```powershell
python -m pip install -e ".[llm]"
# Set provider-specific API keys using your own local environment
python -m examples.live_brainstorm
```

The LiteLLM adapter is opt-in and has not been verified against live providers in this package. Never commit real API secrets, local `.env` files, or private research data. The example HTTP server has **no authentication**—do not expose it to the public Internet without authentication, TLS, rate limits, isolation, and authorization.

## Project layout

```text
pluralforge-ai-v0.4/
├── pluralforge/               # Preferred public Python imports
├── arbiter_plugin/            # Backward-compatible engine
│   ├── adaptive.py            # NEW: estimated net-value router
│   ├── collaboration.py       # New proposals, dissent, orchestration and scoring
│   ├── novelty.py             # NEW: non-destructive duplicate wording flags
│   ├── brainstorm_agents.py   # Scripted agents and optional LiteLLM adapter
│   ├── core.py, models.py     # Deterministic decision evaluation contracts
│   ├── information.py        # Explicit research-value calculator
│   ├── feedback.py           # SQLite verified outcomes
│   ├── api.py, mcp_server.py  # Optional host interfaces
│   └── benchmark.py          # Core regression scoring
├── examples/                  # Offline + optional real-API demos
├── benchmarks/                # Synthetic baseline comparisons + JSON results
├── tests/                     # Automatic unit/regression tests
├── docs/                      # Architecture, benchmark protocol, static demo
├── .github/workflows/tests.yml
├── pyproject.toml
└── LICENSE
```

## Non-goals and limitations

- **No forced consensus, no all-powerful meta-judge, no automatic execution.** Agent agreement is not equivalent to truth.
- **Not an autonomously calibrated VoI estimator:** next-step forecasts are provided by the host. Future research should evaluate/learn these forecasts using held-out measured outcomes.
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
- [ ] Calibrated information-value forecasts with out-of-sample testing
- [ ] Pluggable semantic equivalence and evidence-checking evaluators
- [ ] Provider-specific hard spend caps, robust rate limiting, authentication, and audited deployments

**License:** MIT. See [LICENSE](LICENSE). Contributions are welcome with reproducible tests, clear failure cases and explicit source boundaries.
