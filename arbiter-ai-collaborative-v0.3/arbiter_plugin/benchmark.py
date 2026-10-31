"""Offline reproducible tests against independently specified target outcomes."""
from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, Field
from .models import DecisionRequest
from .core import evaluate_decision

class BenchmarkRow(BaseModel):
    request: DecisionRequest
    expected_option_id: str | None
    expected_status: str

class BenchmarkReport(BaseModel):
    samples: int
    selected_accuracy: float
    status_accuracy: float
    pass_rate_both: float
    failures: list[str] = Field(default_factory=list)


def evaluate_benchmark(rows: list[BenchmarkRow]) -> BenchmarkReport:
    if not rows:
        raise ValueError('Benchmark requires at least one sample')
    selected_ok = status_ok = both_ok = 0
    failures = []
    for row in rows:
        got = evaluate_decision(row.request)
        sel = got.selected_option_id == row.expected_option_id
        stat = got.status == row.expected_status
        selected_ok += sel
        status_ok += stat
        both_ok += sel and stat
        if not sel or not stat:
            failures.append(row.request.decision_id)
    return BenchmarkReport(samples=len(rows), selected_accuracy=selected_ok/len(rows),
                           status_accuracy=status_ok/len(rows), pass_rate_both=both_ok/len(rows),
                           failures=failures)


def load_jsonl(path: str | Path) -> list[BenchmarkRow]:
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    return [BenchmarkRow.model_validate(json.loads(line)) for line in lines if line.strip()]
