"""Demonstrates idempotent verified feedback and domain-specific reputation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from arbiter_plugin import FeedbackStore, Opinion, VerifiedOutcome

if __name__ == '__main__':
    with TemporaryDirectory() as tmp:
        store = FeedbackStore(Path(tmp) / 'feedback.sqlite')
        receipt = store.record(VerifiedOutcome(
            decision_id='example-case-001', domain='education', verified=True,
            verification_source='externally-checked-rubric-001', ground_truth_option_id='option_a',
            opinions=[Opinion(agent_id='agent_a', option_id='option_a'),
                      Opinion(agent_id='agent_b', option_id='option_b')]))
        print(receipt.model_dump_json(indent=2))
