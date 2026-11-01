"""Opt-in, bounded Docker experiment runner with blackboard feedback.

The caller (trusted host) supplies candidate Python source and a trusted benchmark
script. Docker is required; this module fails closed if it cannot launch a
restricted container. It is NOT a proof of strong security against hostile code.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .blackboard import SharedBlackboard


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    candidate_sha256: str
    benchmark_sha256: str
    passed: bool
    metrics: dict[str, float]
    return_code: int | None
    reason: str


class DockerExperimentRunner:
    """Run a trusted benchmark against an untrusted candidate using Docker.

    No API/network credentials are passed into the container. Host must vet the
    fixed image and benchmark, control invocation, and enforce its own quotas.
    This runner NEVER commits, merges, or deploys the candidate.
    """
    def __init__(self, *, image: str = 'python:3.12-alpine',
                 timeout_seconds: int = 30, memory: str = '256m',
                 docker_executable: str = 'docker'):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._/@:-]{0,150}', image):
            raise ValueError('invalid image')
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 120:
            raise ValueError('timeout_seconds must be in 1..120')
        if memory not in {'128m', '256m', '512m'}:
            raise ValueError('memory must be 128m, 256m or 512m')
        if docker_executable != 'docker':
            raise ValueError('only the Docker CLI is supported')
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory = memory
        self.docker_executable = docker_executable

    @staticmethod
    def _digest(source: str) -> str:
        return hashlib.sha256(source.encode('utf-8')).hexdigest()

    def run(self, experiment_id: str, candidate_source: str,
            benchmark_source: str) -> ExperimentResult:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}', experiment_id):
            raise ValueError('invalid experiment_id')
        for name, source in [('candidate', candidate_source), ('benchmark', benchmark_source)]:
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f'{name} must be nonempty Python source')
            if len(source.encode('utf-8')) > 65536:
                raise ValueError(f'{name} exceeds 64 KiB')
        csha, bsha = self._digest(candidate_source), self._digest(benchmark_source)
        with tempfile.TemporaryDirectory(prefix='pluralforge-experiment-') as root:
            folder = Path(root)
            folder.chmod(0o755)  # allow the container UID to traverse
            (folder / 'candidate.py').write_text(candidate_source, encoding='utf-8')
            (folder / 'benchmark.py').write_text(benchmark_source, encoding='utf-8')
            (folder / 'candidate.py').chmod(0o644)
            (folder / 'benchmark.py').chmod(0o644)
            # Python's -I avoids site/user imports; Docker's controls isolate
            # network, files, capabilities, user and bounded resources.
            command = [
                self.docker_executable, 'run', '--rm',
                '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--pids-limit', '64',
                '--memory', self.memory, '--cpus', '1', '--user', '65534:65534',
                '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m',
                '--mount', f'type=bind,source={folder.resolve()},target=/workspace,readonly',
                '--workdir', '/workspace', self.image,
                'python', '-I', 'benchmark.py',
            ]
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True, encoding='utf-8',
                    errors='replace', timeout=self.timeout_seconds,
                    check=False,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as error:
                return ExperimentResult(experiment_id, csha, bsha, False, {}, None,
                                        f'executor unavailable or timed out: {type(error).__name__}')
        if completed.returncode != 0:
            return ExperimentResult(experiment_id, csha, bsha, False, {},
                                    completed.returncode, 'benchmark process failed')
        try:
            # Benchmark must print a single compact JSON object on stdout:
            # {"passed": true, "metrics": {"accuracy": 0.9}}
            if len(completed.stdout) > 16384:
                raise ValueError('oversized benchmark output')
            data = json.loads(completed.stdout)
            if type(data) is not dict or type(data.get('passed')) is not bool:
                raise ValueError('invalid benchmark schema')
            raw = data.get('metrics', {})
            if not isinstance(raw, dict) or len(raw) > 32:
                raise ValueError('invalid metrics')
            import math
            metrics = {}
            for k, v in raw.items():
                if not isinstance(k, str) or len(k) > 80 or type(v) not in (int, float):
                    raise ValueError('invalid metric')
                if not math.isfinite(float(v)):
                    raise ValueError('nonfinite metric')
                metrics[k] = float(v)
            return ExperimentResult(experiment_id, csha, bsha, data['passed'],
                                    metrics, completed.returncode, 'completed')
        except (ValueError, TypeError, json.JSONDecodeError):
            return ExperimentResult(experiment_id, csha, bsha, False, {},
                                    completed.returncode, 'invalid benchmark output')


def record_experiment(board: SharedBlackboard, result: ExperimentResult, *,
                      actor: str = 'experiment_runner') -> None:
    """Append an immutable-ish record and event; trust stays unverified.

    experiment_id is a one-shot key per workspace; reruns use a new ID.
    Host validation must independently verify performance claims.
    """
    from dataclasses import asdict
    board.put(f'experiment:{result.experiment_id}', 'experiment_result',
              asdict(result), actor=actor, expected_version=0)
    board.publish('benchmark.completed',
                  {'experiment_id': result.experiment_id, 'passed': result.passed,
                   'metrics': result.metrics, 'candidate_sha256': result.candidate_sha256,
                   'evidence_status': 'unverified'},
                  actor=actor, key=f'experiment:{result.experiment_id}',
                  dedupe_key=f'benchmark:{result.experiment_id}')
