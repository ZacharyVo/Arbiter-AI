# Design notes: generic decision plugin

## What this package owns

The package owns **decision policy**, not task-specific knowledge. Inputs are validated into stable option IDs; opinions (if present) are normalized as those IDs. A deterministic scorer compares coherent utility and cost units. A separate information planner recommends whether additional evidence is worth obtaining. A feedback component records externally labeled results without putting the AI in charge of marking its own answers correct.

## What the host application owns

The host owns user authorization, domain context, proposed candidates, evidence retrieval, rubric calibration, score estimation, risk policies, actual model/API calls, external actions, time-sensitive ground truth and privacy controls.

## Two decision modes

- `utility`: independent utility/rubric ranking, then deterministic vote-based diagnostic. This is NOT the same as popularity vote.
- `consensus`: reputation-weighted aggregation over stable option IDs, then net utility tie-break. This does NOT guarantee correctness.

## Math

* `Q(a) = E[U(a)] − C(a) − λR(a)`; all quantities in a common utility unit.
* `H = −Σ p(i) log₂ p(i) / log₂(min(number_of_options, number_of_responses))`; diversity only, abstentions excluded.
* `p(reliable | observations) ≈ (correct + 1) / (total + 2)`; Beta(1,1) historical-smoothed accuracy, not context-aware reliability.
* `Net information value = estimated EVSI − research_cost_utility`, only if estimated API spend fits the separate USD cap. EVSI is an external estimate and has NOT been statistically learned here.

## Plugin boundaries

Python SDK = reference implementation; MCP/REST = serialization and transport adapters; LiteLLM = an OPTIONAL opinion supplier. No module in the core ever imports LiteLLM, MCP or FastAPI. Domain implementations should extend with `utility_fn` / `feasibility_fn` and with independent option proposals or evidence sources. Keep persistent user-profiles and private knowledge outside a shared plugin by default.

## Safety / failures

- Schema validation rejects unknown option IDs, duplicate option IDs, duplicate agent IDs, invalid rubric scores.
- Infeasible options are not proposed. A `risk_flag` or host review policy changes result status to `needs_review` without executing anything.
- The host must enforce the review status; an LLM cannot be trusted to honor it by itself.
- Public HTTP endpoints need authentication, isolation, rate limiting, TLS, and abuse monitoring before deployment. `stdio` MCP server is local by default.
- Confidence from a model's own JSON is uncalibrated. Token logprobs, if present, are not the chance the whole answer is correct.
- SQL data is parameterized; feedback writes are deduplicated and conflicting updates rejected.

## Future research

Strongest next step: controlled task sets with independently verified labels and repeated trials. Evaluate the end-to-end *system* against baselines (single agent; majority vote; deterministic scoring; agent+review) before claiming multi-agent superiority.
