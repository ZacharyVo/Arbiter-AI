from pathlib import Path
from arbiter_plugin.benchmark import load_jsonl, evaluate_benchmark

def test_generic_cross_domain_benchmark():
    path=Path(__file__).parent.parent/'benchmarks'/'sample_cases.jsonl'
    report=evaluate_benchmark(load_jsonl(path))
    assert report.samples==5
    assert report.pass_rate_both==1.0
