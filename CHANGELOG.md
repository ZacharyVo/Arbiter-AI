# Changelog

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
