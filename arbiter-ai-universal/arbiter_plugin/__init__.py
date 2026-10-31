"""Arbiter AI Universal: a provider-agnostic decision scoring and evaluation plugin."""
from .models import (Option, Opinion, DecisionRequest, DecisionResult, ResearchOption,
                     ResearchRequest, ResearchRecommendation, VerifiedOutcome, OutcomeReceipt)
from .core import evaluate_decision, disagreement_entropy
from .information import plan_information
from .feedback import FeedbackStore

__version__ = '0.2.0'
__all__ = ['Option','Opinion','DecisionRequest','DecisionResult','ResearchOption','ResearchRequest',
           'ResearchRecommendation','VerifiedOutcome','OutcomeReceipt','evaluate_decision',
           'disagreement_entropy','plan_information','FeedbackStore']
