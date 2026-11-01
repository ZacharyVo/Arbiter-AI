import json
import subprocess
from dataclasses import asdict
from pathlib import Path
import pytest
from arbiter_plugin import SharedBlackboard
from arbiter_plugin.experiments import DockerExperimentRunner, ExperimentResult, record_experiment


def test_runner_uses_restricted_docker_command(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen['cmd'] = cmd
        seen['kwargs'] = kwargs
        source = Path(cmd[cmd.index('--mount') + 1].split('source=')[1].split(',target=')[0])
        assert (source / 'candidate.py').read_text() == 'VALUE = 42\n'
        assert (source / 'benchmark.py').read_text() == 'print("testing")\n'
        return subprocess.CompletedProcess(cmd, 0,
            json.dumps({'passed': True, 'metrics': {'quality': 0.96}}), '')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    result = DockerExperimentRunner().run(
        'sample', 'VALUE = 42\n', 'print("testing")\n')
    assert result.passed and result.metrics == {'quality': 0.96}
    assert all(x in seen['cmd'] for x in ['--network', 'none', '--read-only', '--cap-drop', 'ALL'])
    assert '--user' in seen['cmd'] and '--memory' in seen['cmd']
    assert seen['kwargs']['timeout'] == 30


def test_runner_does_not_trust_invalid_output(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess(a[0], 0, '{"passed":true,"metrics":{"q":"bad"}}', ''))
    r = DockerExperimentRunner().run('s', 'print(1)', 'print(2)')
    assert not r.passed and r.reason == 'invalid benchmark output'


def test_runner_fails_closed_without_docker(monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError('docker')
    monkeypatch.setattr(subprocess, 'run', unavailable)
    r = DockerExperimentRunner().run('s', 'print(1)', 'print(2)')
    assert not r.passed and r.return_code is None


def test_runner_invalid_inputs():
    r = DockerExperimentRunner()
    with pytest.raises(ValueError):
        r.run('bad id', 'x=1', 'print(1)')
    with pytest.raises(ValueError):
        r.run('a', 'x' * 70000, 'print(1)')
    with pytest.raises(ValueError):
        DockerExperimentRunner(memory='2g')
    with pytest.raises(ValueError):
        DockerExperimentRunner(docker_executable='bash')


def test_record_result_stays_unverified_and_notifies(tmp_path):
    board = SharedBlackboard(tmp_path / 'test.sqlite', 'experiment')
    result = ExperimentResult('trial1', 'c'*64, 'b'*64, True,
                              {'quality': 0.92}, 0, 'completed')
    record_experiment(board, result)
    artifact = board.get('experiment:trial1')
    assert artifact.value == asdict(result)
    assert artifact.evidence_status == 'unverified'
    events = board.poll('critic', kinds=('benchmark.completed',))
    assert len(events) == 1
    assert events[0].payload['evidence_status'] == 'unverified'
    with pytest.raises(Exception):
        record_experiment(board, result)
