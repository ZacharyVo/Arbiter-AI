"""SQLite evidence-gated, idempotent feedback; never store questions or secrets."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .models import VerifiedOutcome, OutcomeReceipt

class FeedbackStore:
    def __init__(self, path: str | Path = 'arbiter_feedback.sqlite'):
        self.path = str(path)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS outcomes (
                decision_id TEXT NOT NULL, domain TEXT NOT NULL, agent_id TEXT NOT NULL,
                predicted TEXT, truth TEXT NOT NULL, correct INTEGER,
                verification_source TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(decision_id, agent_id))''')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def reliability(self, domain: str) -> dict[str, float]:
        with self._connect() as db:
            rows = db.execute('''SELECT agent_id, COUNT(correct), SUM(correct)
                                 FROM outcomes WHERE domain=? AND correct IS NOT NULL
                                 GROUP BY agent_id''', (domain,)).fetchall()
        return {agent: (int(correct) + 1) / (int(count) + 2)
                for agent, count, correct in rows}

    def record(self, outcome: VerifiedOutcome) -> OutcomeReceipt:
        if not outcome.verified or not outcome.verification_source.strip():
            raise ValueError('Feedback requires verified=true and an independent verification_source')
        if len({x.agent_id for x in outcome.opinions}) != len(outcome.opinions):
            raise ValueError('Duplicate agent feedback')
        inserted = 0
        with self._connect() as db:
            for op in outcome.opinions:
                existing = db.execute('SELECT domain, truth, predicted FROM outcomes WHERE decision_id=? AND agent_id=?',
                                      (outcome.decision_id, op.agent_id)).fetchone()
                if existing:
                    if existing != (outcome.domain, outcome.ground_truth_option_id, op.option_id):
                        raise ValueError('Conflicting update for an already recorded decision/agent')
                    continue
                correct = None if op.option_id is None else int(op.option_id == outcome.ground_truth_option_id)
                db.execute('''INSERT INTO outcomes(decision_id,domain,agent_id,predicted,truth,correct,verification_source)
                           VALUES (?,?,?,?,?,?,?)''',
                           (outcome.decision_id, outcome.domain, op.agent_id, op.option_id,
                            outcome.ground_truth_option_id, correct, outcome.verification_source))
                inserted += 1
        return OutcomeReceipt(recorded_count=inserted, domain=outcome.domain,
                              reliability=self.reliability(outcome.domain))
