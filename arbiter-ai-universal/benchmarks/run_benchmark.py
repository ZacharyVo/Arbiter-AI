from pathlib import Path
from arbiter_plugin.benchmark import load_jsonl, evaluate_benchmark
if __name__ == '__main__':
    path = Path(__file__).parent / 'sample_cases.jsonl'
    print(evaluate_benchmark(load_jsonl(path)).model_dump_json(indent=2))
