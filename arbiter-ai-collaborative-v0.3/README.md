# Arbiter AI Collaborative · v0.3

**A domain-neutral, provider-neutral collaboration and decision layer for multi-agent AI.**  
**通用多 Agent 头脑风暴与决策插件：允许新方案、保留分歧、使用可解释的成本和风险评分。**

![Offline interactive demo](docs/preview.png)

> **Key principle:** No "meta-judge" LLM has unilateral authority. Agents explore and challenge, while the deterministic decision engine transparently scores the supplied candidates. It never executes an action.

**Status:** v0.3 research MVP · Python 3.11+ · MIT · offline-first · optional LiteLLM, MCP and localhost REST.

## What's new in v0.3 / 和旧版本的区别

| Feature | Previous decision plugin v0.2 | Collaborative v0.3 |
|---|---|---|
| Agent interaction | Input pre-existing opinions | Independent generation → iterative discussion |
| New solutions | Host supplies options up front | Agents can introduce wholly new options with lineage |
| Conflict | Reputation-weighted voting available | Explicit, unresolved support / opposition preserved |
| Meta-judge | Optional arbiter flow in other branch | **Not required or given final decision power** |
| Score | Transparent utility + cost/risk | Same, but missing estimates **block final selection** |
| Stop discussion | Information value recommendation | Explicit round cap, cost/EVSI gate and novelty plateau |
| Integrations | SDK / MCP / REST / LLM adapter | All retained plus collaboration transcript endpoint |

**This is a reusable library for any decision domain.** No stock, investing, romance, medical or industry-specific logic is embedded in the core. Domain-specific expert rules belong in host applications.

## Quick start on Windows / VS Code

```powershell
# Extract project and enter folder
cd arbiter-ai-collaborative-v0.3
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m examples.collaborative_demo
python -m benchmarks.run_collaboration_benchmark
python -m pytest
```

On macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, followed by the same pip/Python commands. The offline example does not call LLMs or incur API charges.

### Interactive website / GitHub Pages

Open **[`docs/index.html`](docs/index.html)** in a browser. It is a self-contained interactive example: step through three rounds, inspect remaining disagreements, change the hybrid plan's cost and toggle "unknown cost." No backend or API account is necessary. The browser demo is scripted, **not a real live multi-model session**.

To publish the standalone page in GitHub: create a public repository, upload this project's files, then enable **Settings → Pages → Deploy from a branch → main → /docs**. The page can be hosted with static files only.

## 1. Asyncio collaboration SDK

```python
import asyncio
from arbiter_plugin import (
    BrainstormRequest, IdeaDraft, Contribution, Position,
    ScriptedBrainstormAgent, run_brainstorm
)

# Replace ScriptedBrainstormAgent with your own .propose()/.discuss()
# or the optional LiteLLMBrainstormAgent for real model calls.
a = ScriptedBrainstormAgent(
    agent_id="a",
    independent=Contribution(agent_id="a", new_ideas=[
        IdeaDraft(id="simple", title="Simple approach", description="Launch early",
                  expected_utility=75, execution_cost=10,
                  risk_loss=5, feasible=True)
    ], position=Position(support_ids=["simple"]))
b = ScriptedBrainstormAgent(
    agent_id="b",
    independent=Contribution(agent_id="b", new_ideas=[
        IdeaDraft(id="robust", title="Robust approach", description="Ship later",
                  expected_utility=90, execution_cost=30,
                  risk_loss=15, feasible=True)
    ], position=Position(support_ids=["robust"])))

result = asyncio.run(run_brainstorm(
    BrainstormRequest(session_id="demo", objective="Choose delivery plan", max_discussion_rounds=1),
    [a, b]
))
print(result.status, result.selected_idea_id, result.unscored_ids)
print(result.model_dump_json(indent=2))
```

The complete three-agent example is in [`examples/collaborative_demo.py`](examples/collaborative_demo.py). It actually generates a **third idea** in the second phase, preserves three sets of dissent, ranks the candidates, and stops when externally estimated marginal discussion value falls below its cost.

### Decision score / 评分公式

For fully specified ideas only:

`net_utility = expected_utility − execution_cost − risk_aversion × risk_loss`

变量含义：预期效用是方案可能带来的价值，执行成本是实现方案的代价，`risk_loss` 是风险损失的给定估计，`risk_aversion` 表示你希望对风险追加的惩罚倍数。**所有数值必须使用可比较的同一单位**，例如都转成“效用点”。没有可靠估值时，系统返回 `needs_estimates`，不会自己创造数值。

### Preserving dissent / 不强制共识

`Contribution` includes `new_ideas`, `critiques` and `position` (supported IDs, opposed IDs and a public note). The latest opposing positions persist in `BrainstormResult.dissents`, while complete round transcripts are returned in `traces`. A risk warning can require review without wiping out the challenged proposal.

### Stopping deliberation / 什么时候继续讨论？

`BrainstormRequest.round_information_estimates` optionally accepts an `InformationEstimate` for each discussion round: externally estimated expected decision gain, deliberation cost in the **same utility unit**, and an estimated API cost in USD. If expected gain is no greater than cost, the next round does not run. When this estimate isn't supplied, the limit/novelty criteria still apply. **This is cost-aware orchestration, not an automatic or calibrated calculation of VoI.**

## 2. External-agent transcript API

Existing agents can generate a transcript themselves and then call the pure function:

```python
from arbiter_plugin import BrainstormRequest, RoundTrace, consolidate_brainstorm

request = BrainstormRequest(session_id="external", objective="Evaluate alternatives")
traces = [RoundTrace(round_number=0, phase="independent", contributions=[])]
result = consolidate_brainstorm(request, traces)
```

This same reducer is available as an optional localhost HTTP endpoint:

```powershell
python -m pip install -e ".[api]"
python -m uvicorn arbiter_plugin.api:app --host 127.0.0.1 --port 8000
# POST /v1/brainstorm {"request": {...}, "traces": [...]}
# GET  /docs         Swagger API browser
```

The endpoint **only consolidates/validates submitted transcripts**; it does not run LLMs. The HTTP demo has no authentication: never expose it directly to the Internet or bind to `0.0.0.0` without implementing auth, TLS, request quotas and isolation.

## 3. MCP tools for AI clients

```powershell
python -m pip install -e ".[mcp]"
python -m arbiter_plugin.mcp_server
```

MCP tool names: `arbiter_brainstorm`, `arbiter_evaluate`, `arbiter_plan_research`, `arbiter_record_verified_outcome`. The new `arbiter_brainstorm` receives the structured `{"request": ..., "traces": ...}` transcript and returns candidate lineage, all dissent, scores and review/missing-data gates.

The MCP adapter targets the optional MCP Python SDK v2. **A live MCP-host handshake has not been verified in this build environment**. MCP does not automatically install a ChatGPT plugin or publish an application.

## 4. Real LLM collaboration (explicit opt-in)

```powershell
python -m pip install -e ".[llm]"
$env:ARBITER_MODELS = "openai/<VALID_MODEL_ID>,anthropic/<VALID_MODEL_ID>,gemini/<VALID_MODEL_ID>"
$env:ARBITER_API_BUDGET_USD = "0.25"
$env:ARBITER_CALL_RESERVATION_USD = "0.04"
python -m examples.live_brainstorm
```

Set your providers' API keys in local environment variables first. Nothing sends data until you run the optional live example. Provider charges and API availability vary. The reservation is **not a provider-enforced hard cap**. Set provider billing controls separately. The live adapter handles JSON, but model-generated content may be invalid and its self-reported utility/confidence is **not** a benchmark or externally verified fact. This optional paid path has **not** been end-to-end tested against live providers in the current environment.

## 5. Feedback and benchmark

The existing `FeedbackStore` uses a local SQLite database with **verified** outcomes to derive Beta-smoothed historical reliability, intended for future evaluation; it does not secretly self-train, alter the decision, or override dissent. `benchmarks/run_collaboration_benchmark.py` contains **five synthetic specification checks** and `tests/` contains deterministic unit tests. They do **not** establish real-model accuracy or superiority over a single LLM.

```powershell
python -m benchmarks.run_collaboration_benchmark
python -m pytest
```

For meaningful future evaluation, use independent human-labeled tasks across domains, blind evaluators, controlled budgets, repeated seeds, a single-model baseline, and metrics for solution novelty, utility, missing evidence, runtime, API cost and safety.

## Modules

```text
arbiter-ai-collaborative-v0.3/
├── arbiter_plugin/
│   ├── collaboration.py       # Independent -> debate -> new ideas -> dissent -> score
│   ├── brainstorm_agents.py   # Scripted + optional LiteLLM implementation
│   ├── models.py, core.py     # Original general-purpose decision contracts/scorer
│   ├── information.py        # Separate supplied-EVSI research planner
│   ├── feedback.py           # Verified feedback SQLite storage
│   ├── benchmark.py          # Existing offline evaluation helper
│   ├── api.py                # Optional local FastAPI interface
│   └── mcp_server.py         # Optional MCP v2 tool adapter
├── examples/
│   ├── collaborative_demo.py # Real offline end-to-end cycle
│   └── live_brainstorm.py    # Optional paid-provider path
├── benchmarks/
├── tests/
├── docs/
│   ├── index.html            # Browser-based interactive example
│   ├── preview.png
│   └── ARCHITECTURE.md
├── .github/workflows/tests.yml
├── pyproject.toml
└── LICENSE
```

## Limitations / research agenda

- "Novelty" is based on distinct structured **IDs**, not semantic uniqueness. Semantic clustering and truly grounded idea evaluation remain future work.
- Agents can be correlated; a crowd of agreeing LLMs can be wrong. Dissent is not itself proof of quality.
- Costs, probabilities, expected information value and risk numbers are only as good as the supplied estimators. The engine does not validate real-world economic usefulness.
- External tools, web search, payments, financial transactions or deployments are **not executed** by this package.
- Review/authorization controls belong to the host. Do not use unsupported autonomous execution for financial, medical or other high-impact settings.
- Core Python tests and browser interactions were run locally. Paid LLM APIs, external MCP-host handshake, authenticated public hosting and real-domain decision-quality benchmarks remain unverified.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full decision flow and trust boundaries.

**License:** MIT. Neither this release nor its model adapters is published as a ChatGPT plugin-store application.
