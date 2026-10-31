# Benchmark Protocol — from synthetic fixtures to credible evidence

**Current status:** `python -m benchmarks.compare_policies` is a fully offline **software test**, not proof of improved AI capability. All cases, predictions, costs and payoffs are scripted. Matching the budget cap is not the same as matching actual token spend.

## Testable hypotheses

H1. With the same money/time budget, cost-aware collaborative decision-making improves externally judged solution quality over a single model, voting, and fixed-round discussion.

H2. Adaptive routing reduces total API cost for a *fixed minimum decision-quality threshold*.

H3. Independent brainstorming + cross-examination generates more **verified nontrivial new options** than independently sampling the same number of model completions.

These hypotheses can all be falsified; do not report success without held-out independent observations.

## Baselines

1. One provider model with a fixed prompt and budget cap.
2. Independent multi-model sampling and plurality vote (including tie/abstain policy).
3. Fixed multi-agent discussion with the same maximum budget.
4. PluralForge adaptive routing with frozen value forecasts and the same budget.
5. Ablation: adaptive routing without discussion; discussion without retrieval; random route with matched cost.

Control not only the cap but, in separate cohorts, the **actual spend** and wall-clock time. Record model IDs, API versions, timeouts, tool permissions, retrieval corpus snapshots, prompt hashes, temperatures, seeds where available, input/output tokens, and failures.

## Evaluation protocol

- Build a preregistered task bank spanning at least software, planning, research synthesis, and resource allocation; include open-ended tasks and situations where abstaining is best.
- Split by task origin and time into development, calibration, and sealed holdout. Avoid overlapping prompts, known benchmark questions, or post-outcome leakage.
- For tasks with objective outcomes, derive labels from independently verified external results; for subjective solutions, obtain multiple blinded human raters who cannot see the policy name or agent count.
- Track distinct *verified* feasible proposals. Compare new proposals to original choices using human/NLI review and provenance—not simply different IDs.
- Measure quality, decision regret where ground truth exists, calibration (Brier for probabilistic events), risk constraint violations, hallucinated citations, abstention correctness, novel idea precision, exact USD spend, tokens, tool calls, latency and refusal/error rates.
- For each model/policy run multiple independent trials and provide uncertainty intervals and paired task comparisons. Account for correlation between models using the same base model or shared evidence.
- Record what the host forecast VoI **before** each action, and estimate observed incremental benefit **afterwards**. Report calibration and rank correlation of predicted vs observed improvement, separately from total decision quality.
- Limit maximum deliberation rounds and provider spend. If models cannot be accessed with comparable context/rules, explicitly flag comparability limits.
- Preserve counterexamples and negative results; never cherry-pick screenshots.

## Reproduction

```bash
python -m benchmarks.compare_policies --output benchmarks/offline_comparison.json
python -m pytest
```

The included synthetic five-scenario example is deliberately small and hand-designed to exercise the path `novel idea -> better scored option -> cheaper targeted continuation`. It is **not randomly sampled** and may favor the implementation by construction. Real evidence requires the controls above.
