"""Optional localhost HTTP adapter. Do not expose to the Internet without auth/TLS."""
from __future__ import annotations
import os
from .models import DecisionRequest, DecisionResult, ResearchRequest, ResearchRecommendation, VerifiedOutcome, OutcomeReceipt
from .core import evaluate_decision
from .information import plan_information
from .feedback import FeedbackStore


def create_app():
    from fastapi import FastAPI
    app = FastAPI(title='Arbiter AI Universal', version='0.2.0')

    @app.post('/v1/evaluate', response_model=DecisionResult)
    def evaluate(req: DecisionRequest):
        return evaluate_decision(req, FeedbackStore(os.getenv('ARBITER_DB', 'arbiter_feedback.sqlite')).reliability(req.domain))

    @app.post('/v1/research', response_model=ResearchRecommendation)
    def research(req: ResearchRequest):
        return plan_information(req)

    # Feedback is intentionally not exposed over unauthenticated HTTP in v0.2.
    return app

try:
    app = create_app()
except ImportError:  # FastAPI only installed with [api]
    app = None
