# Changelog

## 0.5.0 — Information Value Learning Engine

- Added `arbiter_plugin.value_learning`: host-attested evidence logging in local SQLite, idempotent writes, strict as-of data availability checks and context/domain/unit isolation.
- Added regularized, uncertainty-penalized historical marginal-gain forecasts for `consult_agent`, `discuss_all`, and `retrieve`, plus cold-start abstention and optional explicit host priors.
- Integrated learned next-step forecasts into `run_brainstorm`, preserving explicit host forecast overrides and budget caps.
- Added local HTTP and optional MCP interfaces to record verified feedback and request evidence-aware forecasts or routes.
- Added synthetic offline demo, chronological logged-action replay, new regression tests and methodology documentation.
- Core deliberately remains observational: no causal claims, no automatic self-certification, no provider API spending guarantees.

## 0.4.0 — PluralForge AI (research MVP)

- Renamed distribution and public positioning to **PluralForge AI**, retaining `arbiter_plugin` for backwards imports and adding `pluralforge` alias.
- Added explicit next-action planner: consult one agent, discuss with all, retrieve evidence, or stop.
- Added optional adaptive execution in `run_brainstorm`, including source-tracked external research observations.
- Added conservative surface-text novelty warnings (no forced merging).
- Account for reported API charges from rejected but parsed responses, rather than hiding their cost.
- Added local HTTP `POST /v1/next-step` and optional MCP `pluralforge_plan_next_step`.
- Added offline scripted policy comparison across multiple synthetic domains, a full benchmark protocol and adaptive SDK examples.
- Preserved separate utility-point costs versus cash-denominated API budgets.

**Research limits:** No learned VoI, production auth, live provider validation or real LLM benchmark superiority claim.
