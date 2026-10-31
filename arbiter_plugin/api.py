"""Optional LOCAL-only FastAPI adapter (no auth; never expose publicly)."""
from __future__ import annotations
import os
from pydantic import BaseModel, Field
from .models import DecisionRequest, DecisionResult, ResearchRequest, ResearchRecommendation
from .core import evaluate_decision
from .information import plan_information
from .feedback import FeedbackStore
from .collaboration import BrainstormRequest, RoundTrace, BrainstormResult, consolidate_brainstorm
from .adaptive import NextActionEstimate, RouteDecision, select_next_action


class RoutePayload(BaseModel):
    forecasts: list[NextActionEstimate]
    remaining_api_budget_usd: float = Field(ge=0)
    agent_reservations_usd: dict[str, float]
    retriever_available: bool = False
    minimum_net_gain: float = Field(default=0, ge=0)


class TranscriptPayload(BaseModel):
    request: BrainstormRequest
    traces: list[RoundTrace] = Field(default_factory=list)


def create_app():
    from fastapi import FastAPI, HTTPException
    app = FastAPI(title='PluralForge AI', version='0.4.0')

    @app.post('/v1/evaluate', response_model=DecisionResult)
    def evaluate(req: DecisionRequest):
        return evaluate_decision(req, FeedbackStore(os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite')).reliability(req.domain))

    @app.post('/v1/research', response_model=ResearchRecommendation)
    def research(req: ResearchRequest):
        return plan_information(req)

    @app.post('/v1/next-step', response_model=RouteDecision)
    def next_step(payload: RoutePayload):
        return select_next_action(payload.forecasts,
            remaining_api_budget_usd=payload.remaining_api_budget_usd,
            reservations_usd=payload.agent_reservations_usd,
            retriever_available=payload.retriever_available,
            minimum_net_gain=payload.minimum_net_gain)

    @app.post('/v1/brainstorm', response_model=BrainstormResult)
    def brainstorm(payload: TranscriptPayload):
        """Offline consolidate a host-generated transcript; does not call LLMs."""
        try:
            return consolidate_brainstorm(payload.request, payload.traces)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app

try:
    app = create_app()
except ImportError:
    app = None
