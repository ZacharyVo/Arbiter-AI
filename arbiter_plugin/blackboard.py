"""Durable, domain-neutral shared environment for opt-in multi-agent collaboration.

SQLite is the source of truth. Events are append-only, snapshots are versioned,
and acknowledgements are durable per consumer. This module NEVER executes code,
calls an LLM, or treats an agent claim as independently verified evidence.
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping


@dataclass(frozen=True)
class Artifact:
    key: str
    kind: str
    value: Any
    version: int
    updated_by: str
    evidence_status: str
    verification_ref: str | None


@dataclass(frozen=True)
class Event:
    id: int
    kind: str
    actor: str
    key: str | None
    payload: Any
    caused_by: int | None


class VersionConflict(ValueError):
    """A writer used a stale expected_version."""


class SharedBlackboard:
    """A SQLite blackboard scoped to one named workspace.

    Use separate space names for unrelated projects. put() is compare-and-swap:
    pass expected_version=0 for a new key, or the version previously read.
    Event consumers use independent durable cursors; delivery is *at least once*
    until ack(), so side-effecting handlers must be idempotent.
    """

    def __init__(self, path: str | Path, space: str):
        if not space or not space.strip():
            raise ValueError('space must be nonempty')
        self.path = str(path)
        self.space = space
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS board_artifacts (
                    space TEXT NOT NULL, key TEXT NOT NULL, kind TEXT NOT NULL,
                    body TEXT NOT NULL, version INTEGER NOT NULL,
                    updated_by TEXT NOT NULL, evidence_status TEXT NOT NULL,
                    verification_ref TEXT,
                    PRIMARY KEY(space, key)
                );
                CREATE TABLE IF NOT EXISTS board_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    space TEXT NOT NULL, kind TEXT NOT NULL,
                    actor TEXT NOT NULL, artifact_key TEXT,
                    payload TEXT NOT NULL, caused_by INTEGER,
                    dedupe_key TEXT,
                    UNIQUE(space, dedupe_key)
                );
                CREATE INDEX IF NOT EXISTS idx_board_events_space_id
                  ON board_events(space, id);
                CREATE TABLE IF NOT EXISTS board_offsets (
                    space TEXT NOT NULL, consumer TEXT NOT NULL,
                    event_id INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(space, consumer)
                );
            ''')

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA journal_mode=WAL')
        return db

    @staticmethod
    def _required(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{name} must be nonempty')
        return value

    @staticmethod
    def _json(value: Any) -> str:
        serialized = json.dumps(value, ensure_ascii=False, allow_nan=False,
                                sort_keys=True, separators=(',', ':'))
        if len(serialized.encode('utf-8')) > 65536:
            raise ValueError('payload exceeds 64 KiB; use a content-addressed file reference')
        return serialized

    @staticmethod
    def _artifact(row: tuple) -> Artifact:
        return Artifact(row[0], row[1], json.loads(row[2]), row[3], row[4], row[5], row[6])

    def get(self, key: str) -> Artifact | None:
        with self._connect() as db:
            row = db.execute('''SELECT key, kind, body, version, updated_by,
                               evidence_status, verification_ref FROM board_artifacts
                               WHERE space=? AND key=?''', (self.space, key)).fetchone()
        return self._artifact(row) if row else None

    def list_artifacts(self, kind: str | None = None) -> list[Artifact]:
        query = '''SELECT key, kind, body, version, updated_by, evidence_status,
                   verification_ref FROM board_artifacts WHERE space=?'''
        params: tuple = (self.space,)
        if kind is not None:
            query += ' AND kind=?'
            params += (kind,)
        with self._connect() as db:
            rows = db.execute(query + ' ORDER BY key', params).fetchall()
        return [self._artifact(row) for row in rows]

    def put(self, key: str, kind: str, value: Any, *, actor: str,
            expected_version: int, caused_by: int | None = None) -> Artifact:
        """Atomically update snapshot and publish artifact.created/updated event.

        Agent-authored snapshots start unverified; an independent host must call
        verify() before a record can be labelled host_checked.
        """
        for name, val in [('key', key), ('kind', kind), ('actor', actor)]:
            self._required(val, name)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('expected_version must be a nonnegative integer')
        body = self._json(value)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT version FROM board_artifacts WHERE space=? AND key=?',
                             (self.space, key)).fetchone()
            current = row[0] if row else 0
            if current != expected_version:
                raise VersionConflict(f'{key}: expected {expected_version}, actual {current}')
            version = current + 1
            db.execute('''INSERT INTO board_artifacts
                (space,key,kind,body,version,updated_by,evidence_status,verification_ref)
                VALUES (?,?,?,?,?,?,'unverified',NULL)
                ON CONFLICT(space,key) DO UPDATE SET
                kind=excluded.kind, body=excluded.body, version=excluded.version,
                updated_by=excluded.updated_by, evidence_status='unverified',
                verification_ref=NULL''',
                (self.space, key, kind, body, version, actor))
            event_kind = 'artifact.created' if current == 0 else 'artifact.updated'
            db.execute('''INSERT INTO board_events
                (space,kind,actor,artifact_key,payload,caused_by)
                VALUES (?,?,?,?,?,?)''',
                (self.space, event_kind, actor, key,
                 self._json({'key': key, 'kind': kind, 'version': version}), caused_by))
        return Artifact(key, kind, json.loads(body), version, actor, 'unverified', None)

    def verify(self, key: str, *, verifier: str, evidence_ref: str,
               expected_version: int) -> Artifact:
        """Host-only trust boundary: caller is responsible for independent verification."""
        self._required(verifier, 'verifier')
        self._required(evidence_ref, 'evidence_ref')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT version FROM board_artifacts WHERE space=? AND key=?',
                             (self.space, key)).fetchone()
            if row is None or row[0] != expected_version:
                raise VersionConflict('verification requires the current artifact version')
            db.execute('''UPDATE board_artifacts SET evidence_status='host_checked',
                          verification_ref=? WHERE space=? AND key=?''',
                       (evidence_ref, self.space, key))
            db.execute('''INSERT INTO board_events
                (space,kind,actor,artifact_key,payload) VALUES (?,?,?,?,?)''',
                (self.space, 'artifact.verified', verifier, key,
                 self._json({'key': key, 'version': expected_version,
                             'verification_ref': evidence_ref})))
        return self.get(key)  # type: ignore[return-value]

    def publish(self, kind: str, payload: Any, *, actor: str,
                key: str | None = None, caused_by: int | None = None,
                dedupe_key: str | None = None) -> int:
        """Publish an observation, not an automatically trusted fact.

        dedupe_key makes *identical* event publication idempotent within a space.
        """
        self._required(kind, 'kind')
        self._required(actor, 'actor')
        if key is not None:
            self._required(key, 'key')
        if dedupe_key is not None:
            self._required(dedupe_key, 'dedupe_key')
        body = self._json(payload)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if dedupe_key is not None:
                old = db.execute('''SELECT id,kind,actor,artifact_key,payload,caused_by
                     FROM board_events WHERE space=? AND dedupe_key=?''',
                     (self.space, dedupe_key)).fetchone()
                if old:
                    if old[1:] != (kind, actor, key, body, caused_by):
                        raise ValueError('dedupe_key collision with different content')
                    return old[0]
            cur = db.execute('''INSERT INTO board_events
                (space,kind,actor,artifact_key,payload,caused_by,dedupe_key)
                VALUES (?,?,?,?,?,?,?)''',
                (self.space, kind, actor, key, body, caused_by, dedupe_key))
            return int(cur.lastrowid)

    def cursor(self, consumer: str) -> int:
        self._required(consumer, 'consumer')
        with self._connect() as db:
            row = db.execute('''SELECT event_id FROM board_offsets
                                WHERE space=? AND consumer=?''',
                             (self.space, consumer)).fetchone()
        return row[0] if row else 0

    def poll(self, consumer: str, *, kinds: tuple[str, ...] = (),
             limit: int = 20) -> list[Event]:
        """Read new subscribed events. Does not advance the durable cursor."""
        self._required(consumer, 'consumer')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be between 1 and 100')
        query = '''SELECT id,kind,actor,artifact_key,payload,caused_by
                   FROM board_events WHERE space=? AND id>?'''
        params: list[Any] = [self.space, self.cursor(consumer)]
        if kinds:
            if any(not isinstance(x, str) or not x.strip() for x in kinds):
                raise ValueError('kinds must contain nonempty strings')
            query += ' AND kind IN (' + ','.join('?' * len(kinds)) + ')'
            params += list(kinds)
        params.append(limit)
        with self._connect() as db:
            rows = db.execute(query + ' ORDER BY id LIMIT ?', params).fetchall()
        return [Event(r[0], r[1], r[2], r[3], json.loads(r[4]), r[5]) for r in rows]

    def ack(self, consumer: str, event_id: int) -> None:
        """Advance only after successful processing. Requires a real event in this space."""
        self._required(consumer, 'consumer')
        if type(event_id) is not int or event_id < 1:
            raise ValueError('event_id must be a positive integer')
        with self._connect() as db:
            if not db.execute('SELECT 1 FROM board_events WHERE space=? AND id=?',
                              (self.space, event_id)).fetchone():
                raise ValueError('unknown event')
            db.execute('''INSERT INTO board_offsets(space,consumer,event_id)
                VALUES (?,?,?) ON CONFLICT(space,consumer) DO UPDATE SET
                event_id=MAX(event_id,excluded.event_id)''',
                (self.space, consumer, event_id))


EventHandler = Callable[[Event, SharedBlackboard], Any | Awaitable[Any]]


class EventWorker:
    """Opt-in, bounded event dispatcher. No autonomous background process.

    Handlers should use idempotency keys for external effects: a crash before
    cursor acknowledgement will cause the event to be delivered again.
    """

    def __init__(self, board: SharedBlackboard, consumer: str,
                 handlers: Mapping[str, EventHandler]):
        if not handlers:
            raise ValueError('handlers must be nonempty')
        board._required(consumer, 'consumer')
        self.board = board
        self.consumer = consumer
        self.handlers = dict(handlers)

    async def step(self, *, max_events: int = 10) -> int:
        if type(max_events) is not int or not 1 <= max_events <= 100:
            raise ValueError('max_events must be between 1 and 100')
        done = 0
        while done < max_events:
            events = self.board.poll(self.consumer, kinds=tuple(self.handlers), limit=1)
            if not events:
                break
            event = events[0]
            result = self.handlers[event.kind](event, self.board)
            if inspect.isawaitable(result):
                await result
            self.board.ack(self.consumer, event.id)
            done += 1
        return done
