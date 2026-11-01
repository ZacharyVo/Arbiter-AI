# PluralForge AI v0.7 — Experimental Sandbox / 隔离实验

This optional module enables an approved host to test candidate Python source
against a host-authored benchmark in an ephemeral, constrained Docker container.
It reports JSON metrics to the v0.6 SharedBlackboard and emits a
benchmark.completed event. No branch merges, deployments or model calls occur.

## Security scope

- Requires an **independently installed Docker engine** and an image selected
  by the **trusted host**. There is no automatic fallback to host Python.
- Uses no network, read-only filesystem and input bind mount, non-root UID,
  dropped Linux capabilities, no-new-privileges, and CPU, memory, PID and time limits.
- Docker is **not an absolute security boundary** against malicious code or
  host/kernel vulnerabilities. Run on a dedicated restricted worker or VM.
- The benchmark script is host-supplied and must be reviewed; agent-supplied
  source must not be promoted to production.
- Output is **unverified** until independent host review. Beware adversarial
  benchmark manipulation, inaccurate metrics, stdout forgery and sandbox escape.
- No external secrets or API credentials are provided; enforce separate
  resource, cost and execution quotas at the host level.
- An interrupted Docker CLI may leave a container running; monitor and clean
  orphaned containers before enabling untrusted production workloads.

## Usage

    from pluralforge import SharedBlackboard, DockerExperimentRunner, record_experiment

    board = SharedBlackboard("research.sqlite", "demo")
    source = "def candidate(x): return x * 2"
    benchmark = """
    import json
    from candidate import candidate
    print(json.dumps({"passed": candidate(3)==6,
                      "metrics": {"quality": float(candidate(3)==6)}}))
    """
    result = DockerExperimentRunner().run("trial-001", source, benchmark)
    record_experiment(board, result)
    print(result.passed, board.poll("critic", kinds=("benchmark.completed",)))

The runner expects a single JSON object in stdout, with boolean passed and
up to 32 finite numeric metrics. It does not treat reported success as an
independent verification. Tests mock Docker and do not launch untrusted code.

Run: python -m pytest tests/test_experiments.py -q
