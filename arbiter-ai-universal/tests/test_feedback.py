from pathlib import Path
import pytest
from arbiter_plugin import FeedbackStore, VerifiedOutcome, Opinion


def outcome(**updates):
    a=dict(decision_id='case1',domain='research',ground_truth_option_id='a',verified=True,
           verification_source='benchmark-ground-truth-file',opinions=[
               Opinion(agent_id='x',option_id='a'),Opinion(agent_id='y',option_id='b')])
    a.update(updates)
    return VerifiedOutcome(**a)


def test_feedback_reliability(tmp_path:Path):
    store=FeedbackStore(tmp_path/'outcomes.sqlite')
    result=store.record(outcome())
    assert result.recorded_count==2
    assert result.reliability['x']==2/3
    assert result.reliability['y']==1/3


def test_duplicate_is_idempotent(tmp_path):
    store=FeedbackStore(tmp_path/'outcomes.sqlite')
    store.record(outcome())
    receipt=store.record(outcome())
    assert receipt.recorded_count==0 and receipt.reliability['x']==2/3


def test_unverified_rejected(tmp_path):
    store=FeedbackStore(tmp_path/'outcomes.sqlite')
    with pytest.raises(ValueError):
        store.record(outcome(verified=False))
    with pytest.raises(ValueError):
        store.record(outcome(verification_source=''))


def test_cannot_rewrite_ground_truth(tmp_path):
    store=FeedbackStore(tmp_path/'outcomes.sqlite')
    store.record(outcome())
    with pytest.raises(ValueError):
        store.record(outcome(ground_truth_option_id='b'))
    assert store.reliability('research')['x']==2/3


def test_domain_isolated(tmp_path):
    store=FeedbackStore(tmp_path/'outcomes.sqlite')
    store.record(outcome())
    assert store.reliability('finance')=={}


def test_abstaining_agent_does_not_get_wrong_prediction(tmp_path):
    store=FeedbackStore(tmp_path/'outcomes.sqlite')
    store.record(outcome(opinions=[Opinion(agent_id='x',option_id=None)]))
    assert store.reliability('research')=={}
