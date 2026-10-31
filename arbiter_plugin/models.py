"""Provider-neutral data contracts for decisions, information gathering and feedback."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Option(StrictModel):
    id: str = Field(min_length=1)
    description: str = ''
    # Optional numeric utility: when omitted, weighted rubric criteria may supply it.
    expected_utility: float | None = None
    criterion_scores: dict[str, float] = Field(default_factory=dict,
        description='Explicit supplied rubric scores from 0 to 100, NOT invented by Arbiter')
    execution_cost: float = Field(default=0.0, ge=0.0)
    risk_loss: float = Field(default=0.0, ge=0.0)
    feasible: bool = True
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_rubric(self):
        if any(not (0 <= v <= 100) for v in self.criterion_scores.values()):
            raise ValueError('criterion_scores must be in [0, 100]')
        return self

class Opinion(StrictModel):
    agent_id: str = Field(min_length=1)
    option_id: str | None = None  # None = abstain
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_source: Literal['calibrated', 'self_report', 'unknown'] = 'unknown'
    rationale: str = ''  # User-visible short rationale, not private chain-of-thought
    evidence: list[str] = Field(default_factory=list)
    risk_flag: bool = False

    @model_validator(mode='after')
    def check_confidence(self):
        if self.confidence_source == 'calibrated' and self.confidence is None:
            raise ValueError('calibrated confidence requires a numeric confidence')
        return self

class DecisionRequest(StrictModel):
    decision_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    domain: str = 'general'
    mode: Literal['utility', 'consensus'] = 'utility'
    utility_unit: str = 'points'
    risk_aversion: float = Field(default=1.0, ge=0)
    maximum_risk_loss: float | None = Field(default=None, ge=0)
    require_human_review: bool = False
    options: list[Option] = Field(min_length=1)
    opinions: list[Opinion] = Field(default_factory=list)
    criterion_weights: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_related_fields(self):
        ids = [item.id for item in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError('Option ids must be unique')
        agent_ids = [item.agent_id for item in self.opinions]
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError('Agent ids must be unique per decision')
        if any(op.option_id is not None and op.option_id not in ids for op in self.opinions):
            raise ValueError('Opinion refers to unknown option id')
        if any(v < 0 for v in self.criterion_weights.values()):
            raise ValueError('criterion_weights must be nonnegative')
        for option in self.options:
            if self.mode == 'utility' and option.expected_utility is None:
                if not self.criterion_weights or not any(self.criterion_weights.values()):
                    raise ValueError(f'{option.id}: supply expected_utility or criterion_weights')
                if set(self.criterion_weights) != set(option.criterion_scores):
                    raise ValueError(f'{option.id}: criterion score keys must match weights')
        return self

class OptionScore(StrictModel):
    option_id: str
    base_utility: float
    execution_cost: float
    risk_penalty: float
    net_utility: float
    feasible: bool
    votes: float

class DecisionResult(StrictModel):
    decision_id: str
    status: Literal['proposed', 'needs_review', 'no_feasible_option']
    selected_option_id: str | None
    mode: str
    utility_unit: str
    disagreement_entropy: float = Field(ge=0, le=1)
    scores: list[OptionScore]
    agent_reputation_used: dict[str, float]
    notes: list[str] = Field(default_factory=list)

class ResearchOption(StrictModel):
    id: str = Field(min_length=1)
    description: str = ''
    expected_information_gain: float = Field(ge=0, description='Expected decision improvement in utility units')
    research_cost_utility: float = Field(ge=0, description='Research cost converted into SAME utility units')
    estimated_api_cost_usd: float = Field(default=0, ge=0)
    requires_approval: bool = False

class ResearchRequest(StrictModel):
    decision_id: str = Field(min_length=1)
    utility_unit: str = 'points'
    max_api_budget_usd: float = Field(default=0, ge=0)
    api_spent_usd: float = Field(default=0, ge=0)
    opportunities: list[ResearchOption] = Field(default_factory=list)

class ResearchRecommendation(StrictModel):
    decision_id: str
    action: Literal['research', 'decide_now', 'needs_review']
    recommended_research_id: str | None = None
    expected_net_information_value: float = 0
    notes: list[str] = Field(default_factory=list)

class VerifiedOutcome(StrictModel):
    decision_id: str = Field(min_length=1)
    domain: str = 'general'
    ground_truth_option_id: str = Field(min_length=1)
    verified: bool = False
    verification_source: str = ''
    opinions: list[Opinion]

class OutcomeReceipt(StrictModel):
    recorded_count: int
    domain: str
    reliability: dict[str, float]
