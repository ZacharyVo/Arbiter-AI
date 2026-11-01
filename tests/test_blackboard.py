"""Shared-environment regression tests; no API keys, network, or LLM calls."""
import asyncio
import pytest
from arbiter_plugin.blackboard import EventWorker, SharedBlackboard, VersionConflict


def board(tmp_path, space='project-a'):
    return SharedBlackboard(tmp_path / 'shared.sqlite', space=space)


def test_artifacts_shared_across_agents_and_restarts(tmp_path):
    a = board(tmp_path)
    created = a.put('idea:1', 'idea', {'text': 'try A'}, actor='explorer', expected_version=0)
    b = board(tmp_path)
    assert created.version == 1
    assert b.get('idea:1').value == {'text': 'try A'}
    assert b.get('idea:1').evidence_status == 'unverified'
    changed = b.put('idea:1', 'idea', {'text': 'try B'}, actor='critic', expected_version=1)
    assert changed.version == 2
    assert [x.kind for x in a.poll('observer')] == ['artifact.created', 'artifact.updated']


def test_compare_and_swap_prevents_lost_updates(tmp_path):
    a = board(tmp_path)
    b = board(tmp_path)
    a.put('k', 'proposal', {'n': 1}, actor='a', expected_version=0)
    b.put('k', 'proposal', {'n': 2}, actor='b', expected_version=1)
    with pytest.raises(VersionConflict):
        a.put('k', 'proposal', {'n': 999}, actor='a', expected_version=1)
    assert a.get('k').value == {'n': 2}
    assert len(a.poll('observer')) == 2


def test_namespaced_state_and_events(tmp_path):
    a, b = board(tmp_path, 'A'), board(tmp_path, 'B')
    a.put('same', 'idea', 1, actor='a', expected_version=0)
    b.put('same', 'idea', 2, actor='b', expected_version=0)
    assert a.get('same').value == 1
    assert b.get('same').value == 2
    assert [x.actor for x in a.poll('observer')] == ['a']
    assert [x.actor for x in b.poll('observer')] == ['b']


def test_durable_ack_and_independent_subscriptions(tmp_path):
    a = board(tmp_path)
    a.publish('environment.changed', {'regime': 'volatile'}, actor='watcher')
    a.publish('benchmark.completed', {'score': 51}, actor='tester')
    ids = a.poll('critic', kinds=('benchmark.completed',))
    assert len(ids) == 1 and ids[0].payload == {'score': 51}
    assert len(a.poll('explorer')) == 2
    a.ack('critic', ids[0].id)
    assert board(tmp_path).poll('critic', kinds=('benchmark.completed',)) == []
    assert len(a.poll('explorer')) == 2


def test_redelivery_until_ack(tmp_path):
    a = board(tmp_path)
    a.publish('risk.flagged', {'why': 'unstable'}, actor='critic')
    first = a.poll('reviewer')[0]
    assert a.poll('reviewer')[0].id == first.id
    a.ack('reviewer', first.id)
    a.ack('reviewer', first.id)  # idempotent
    assert a.poll('reviewer') == []
    with pytest.raises(ValueError, match='unknown event'):
        a.ack('reviewer', 10000)


def test_idempotent_publication_and_collision(tmp_path):
    a = board(tmp_path)
    one = a.publish('environment.changed', {'v': 1}, actor='sensor', dedupe_key='sensor/1')
    two = a.publish('environment.changed', {'v': 1}, actor='sensor', dedupe_key='sensor/1')
    assert one == two
    with pytest.raises(ValueError, match='collision'):
        a.publish('environment.changed', {'v': 2}, actor='sensor', dedupe_key='sensor/1')
    assert len(a.poll('watcher')) == 1


def test_new_writes_invalidate_verification(tmp_path):
    a = board(tmp_path)
    a.put('result', 'benchmark', {'pass': True}, actor='agent', expected_version=0)
    verified = a.verify('result', verifier='host', evidence_ref='report:123', expected_version=1)
    assert verified.evidence_status == 'host_checked'
    assert verified.verification_ref == 'report:123'
    new = a.put('result', 'benchmark', {'pass': False}, actor='agent', expected_version=1)
    assert new.evidence_status == 'unverified' and new.verification_ref is None
    with pytest.raises(VersionConflict):
        a.verify('result', verifier='host', evidence_ref='old', expected_version=0)


def test_code_reference_is_data_not_executable(tmp_path):
    a = board(tmp_path)
    ref = {'repo': 'owner/project', 'branch': 'agent/sandbox', 'commit': 'deadbeef',
           'patch_sha256': 'a' * 64}
    a.put('code:experiment-1', 'code_reference', ref,
          actor='builder', expected_version=0)
    assert a.get('code:experiment-1').value == ref


def test_payload_validation_and_limits(tmp_path):
    a = board(tmp_path)
    with pytest.raises(ValueError):
        a.publish('test', float('nan'), actor='a')
    with pytest.raises(ValueError, match='64 KiB'):
        a.publish('test', 'x' * 70000, actor='a')
    with pytest.raises(ValueError, match='expected_version'):
        a.put('x', 'kind', {}, actor='a', expected_version=True)


def test_bounded_worker_emits_reactive_artifacts(tmp_path):
    a = board(tmp_path)
    a.publish('benchmark.completed', {'accuracy': 0.6}, actor='tester')
    a.publish('benchmark.completed', {'accuracy': 0.7}, actor='tester')

    async def inspect(event, board):
        board.put(f'critique:{event.id}', 'critique',
                  {'note': 'validate sample', 'origin': event.id},
                  actor='critic', expected_version=0, caused_by=event.id)

    worker = EventWorker(a, 'critic', {'benchmark.completed': inspect})
    assert asyncio.run(worker.step(max_events=1)) == 1
    assert a.get('critique:1').value['note'] == 'validate sample'
    assert asyncio.run(worker.step(max_events=1)) == 1
    assert asyncio.run(worker.step()) == 0
    assert len(a.list_artifacts('critique')) == 2


def test_worker_failure_does_not_ack(tmp_path):
    a = board(tmp_path)
    eid = a.publish('risk.flagged', {'type': 'regression'}, actor='tester')

    def fail(event, board):
        raise RuntimeError('temporary failure')

    worker = EventWorker(a, 'critic', {'risk.flagged': fail})
    with pytest.raises(RuntimeError):
        asyncio.run(worker.step())
    assert a.cursor('critic') == 0
    assert a.poll('critic')[0].id == eid


def test_worker_rejects_unbounded_loops(tmp_path):
    a = board(tmp_path)
    worker = EventWorker(a, 'critic', {'x': lambda event, board: None})
    with pytest.raises(ValueError):
        asyncio.run(worker.step(max_events=0))
    with pytest.raises(ValueError):
        EventWorker(a, 'empty', {})
