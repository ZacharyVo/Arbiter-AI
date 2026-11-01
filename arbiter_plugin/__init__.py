"""PluralForge AI v0.7.1: cost-aware collective intelligence and decision optimization."""
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
from .adaptive import NextActionEstimate, ActionRank, RouteDecision, select_next_action
from .collaboration import ResearchObservation
from .novelty import NoveltyFlag, surface_duplicate_flags
from .value_learning import (LearningContext, ActionCandidate, VerifiedValueObservation,
                             LearningRequest, ActionForecast, LearningReport, LearningRoute,
                             InformationValueLearner)
from .blackboard import Artifact, Event, SharedBlackboard, EventWorker, VersionConflict
from .experiments import DockerExperimentRunner, ExperimentResult, record_experiment
from .experiment_routing import ExperimentEstimate, UnifiedActionRank, UnifiedRoute, select_research_or_experiment
__version__ = '0.7.1'
__all__ = ['Option', 'Opinion', 'DecisionRequest', 'DecisionResult', 'ResearchOption',
           'ResearchRequest', 'ResearchRecommendation', 'VerifiedOutcome', 'OutcomeReceipt',
           'evaluate_decision', 'disagreement_entropy', 'plan_information', 'FeedbackStore',
           'IdeaDraft', 'Idea', 'CritiqueDraft', 'Critique', 'Position', 'Contribution',
           'InformationEstimate', 'BrainstormRequest', 'DiscussionView', 'RoundTrace',
           'IdeaScore', 'Dissent', 'BrainstormResult', 'consolidate_brainstorm',
           'run_brainstorm', 'ResearchObservation', 'NextActionEstimate', 'ActionRank',
           'RouteDecision', 'select_next_action', 'NoveltyFlag', 'surface_duplicate_flags', 'ScriptedBrainstormAgent', 'LiteLLMBrainstormAgent',
           'LearningContext', 'ActionCandidate', 'VerifiedValueObservation',
           'LearningRequest', 'ActionForecast', 'LearningReport', 'LearningRoute',
           'InformationValueLearner', 'Artifact', 'Event', 'SharedBlackboard',
           'EventWorker', 'VersionConflict', 'DockerExperimentRunner',
           'ExperimentResult', 'record_experiment', 'ExperimentEstimate',
           'UnifiedActionRank', 'UnifiedRoute', 'select_research_or_experiment']
