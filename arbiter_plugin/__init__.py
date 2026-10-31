"""Arbiter AI Collaborative: domain-neutral multi-agent idea exploration and evaluation."""
from .models import (Option, Opinion, DecisionRequest, DecisionResult, ResearchOption,
                     ResearchRequest, ResearchRecommendation, VerifiedOutcome, OutcomeReceipt)
from .core import evaluate_decision, disagreement_entropy
from .information import plan_information
from .feedback import FeedbackStore
from .collaboration import (IdeaDraft, Idea, CritiqueDraft, Critique, Position, Contribution,
                            InformationEstimate, BrainstormRequest, DiscussionView, RoundTrace,
                            IdeaScore, Dissent, BrainstormResult, consolidate_brainstorm,
                            run_brainstorm)
from .brainstorm_agents import ScriptedBrainstormAgent, LiteLLMBrainstormAgent
__version__ = '0.3.0'
__all__ = ['Option', 'Opinion', 'DecisionRequest', 'DecisionResult', 'ResearchOption',
           'ResearchRequest', 'ResearchRecommendation', 'VerifiedOutcome', 'OutcomeReceipt',
           'evaluate_decision', 'disagreement_entropy', 'plan_information', 'FeedbackStore',
           'IdeaDraft', 'Idea', 'CritiqueDraft', 'Critique', 'Position', 'Contribution',
           'InformationEstimate', 'BrainstormRequest', 'DiscussionView', 'RoundTrace',
           'IdeaScore', 'Dissent', 'BrainstormResult', 'consolidate_brainstorm',
           'run_brainstorm', 'ScriptedBrainstormAgent', 'LiteLLMBrainstormAgent']
