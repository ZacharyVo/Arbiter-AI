"""Optional LOCAL-only FastAPI adapter (no auth; never expose publicly)."""
from __future__ import annotations
import os
from pydantic import BaseModel, Field
from .models import DecisionRequest, DecisionResult, ResearchRequest, ResearchRecommendation
from .core import evaluate_decision
from .information import plan_information
from .feedback import FeedbackStore
from .collaboration import BrainstormRequest, RoundTrace, BrainstormResult, consolidate_brainstorm


class TranscriptPayload(BaseModel):
    request: BrainstormRequest
    traces: list[RoundTrace] = Field(default_factory=list)


def create_app():
    from fastapi import FastAPI, HTTPException
    app = FastAPI(title='Arbiter AI Collaborative', version='0.3.0')

    @app.post('/v1/evaluate', response_model=DecisionResult)
    def evaluate(req: DecisionRequest):
        return evaluate_decision(req, FeedbackStore(os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite')).reliability(req.domain))

    @app.post('/v1/research', response_model=ResearchRecommendation)
    def research(req: ResearchRequest):
        return plan_information(req)

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
