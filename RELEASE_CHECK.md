# v0.5 verification checklist

- Python tests: 78 passed (including new Information Value Learning Engine tests).
- New engine demonstrator: `python -m examples.value_learning_demo` completed.
- Chronological synthetic replay: `python -m benchmarks.learning_temporal_replay` completed, forecast coverage 1.0 and held-out observed-action MAE 1.6882 points **in synthetic fixtures only**.
- Python Wheel build: succeeded.
- Wheel installed into isolated temporary target; import and cold-start forecast checks passed.
- Static browser demo: no JavaScript exceptions; sample-threshold and cost slider behavior checked.
- No paid LLM or live MCP client integration was exercised.

Do not treat these as real-world AI accuracy or causal information-value claims.
