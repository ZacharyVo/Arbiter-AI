# Unified next-step routing / 统一信息价值路由

The v0.7.1 additive planning API compares host-supplied or independently
verified-history discussion/retrieval forecasts with explicit, host-supplied
experiment forecasts. It never invents an expected experiment gain and never
executes an experiment automatically.

    from pluralforge import ExperimentEstimate, select_research_or_experiment

    estimate = ExperimentEstimate(
        experiment_id="trial-1", expected_decision_gain=10,
        execution_cost_utility=3, estimated_execution_cost_usd=.10,
        rationale="Host hypothesis, unverified", candidate_ref="git:abc",
        benchmark_ref="benchmark:reviewed")
    route = select_research_or_experiment(
        forecasts=[], experiments=[estimate],
        remaining_api_budget_usd=.05, remaining_experiment_budget_usd=.50,
        reservations_usd={}, experiment_runner_available=True,
        human_approved_experiments=frozenset({"trial-1"}))
    print(route.action, route.target_id)

A host must separately invoke DockerExperimentRunner after examining the
plan. It must assess sandbox risk, benchmark provenance, and enforce spending
budgets externally. Unverified experiment results cannot self-certify
information value. Utility costs and USD cash budgets are never mixed.
This is a standalone planner for host orchestration; the existing
run_brainstorm workflow remains unchanged and does not auto-run experiments.
