# Changelog

## 0.7.1 — Unified next-step recommendation (additive)

- Added advisory experiment-vs-discussion-vs-retrieval-vs-stop router with explicit experiment hypotheses, human approval gating, and independent cash limits.
- Supports passing previously generated value-learning forecasts without treating unverified experiment outputs as learned gains.
- Added deterministic regression tests and usage documentation.
- Existing brainstorm engine does not automatically invoke experiments.


## 0.7.0 — Restricted experiment runner and benchmark feedback

- Added opt-in DockerExperimentRunner for controlled host-approved Python benchmarks and candidate code.
- No network, non-root process, read-only input and container filesystem, dropped capabilities, and resource/time limits.
- Structured benchmark results are stored unverified in the SharedBlackboard; benchmark.completed events notify subscribing agents.
- Tests simulate the Docker CLI and verify restrictions, schema rejection, error behavior and feedback persistence.
- No auto-merge, production execution or independent score attestation. Docker is not a complete hostile-code security guarantee.


## 0.6.0 — Shared Blackboard and event-based coordination

- Added opt-in SQLite SharedBlackboard: scoped versioned artifacts, atomic change events, compare-and-swap updates and content-size validation.
- Added append-only event records, durable per-consumer cursors, filtered subscriptions, idempotent event publishing and a bounded async/sync EventWorker.
- Agents may share ideas, state, benchmark observations and inert references to code branches/commits. No arbitrary code execution, merge or external actions.
- Added host-attested verification metadata; changed artifacts reset to unverified. This is a host-side trust convention, not access control.
- Added offline end-to-end event demo, 12 regression tests and bilingual usage documentation.
- Preserved the independent first round, dissent, cost-aware router, human-review boundaries and existing v0.5 public API.

**Limitations:** no autonomous daemon, server auth, agent tool sandbox, automatic code merge or direct integration into the existing run_brainstorm loop.


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
