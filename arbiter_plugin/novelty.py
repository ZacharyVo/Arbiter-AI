"""Conservative surface-form similarity flags; NOT semantic novelty verification.

The engine never silently merges two options: disagreement and lineage are
preserved, and a human or external similarity service can inspect flags.
"""
from __future__ import annotations
import re
from difflib import SequenceMatcher
from pydantic import BaseModel, Field


class NoveltyFlag(BaseModel):
    idea_id: str
    resembles_id: str
    surface_similarity: float = Field(ge=0, le=1)
    reason: str = 'near_duplicate_surface_text_unverified'


def _normalized(text: str) -> str:
    return ' '.join(re.findall(r'\w+', text.casefold(), flags=re.UNICODE))


def surface_duplicate_flags(ideas, threshold: float = .92) -> list[NoveltyFlag]:
    if not 0 < threshold <= 1:
        raise ValueError('threshold must be in (0,1]')
    flags=[]
    for idx, idea in enumerate(ideas):
        # Title+description: a different name alone is not novel.
        current = _normalized(idea.title+' '+idea.description)
        for older in ideas[:idx]:
            previous = _normalized(older.title+' '+older.description)
            similarity = SequenceMatcher(None,current,previous,autojunk=False).ratio()
            if similarity >= threshold:
                flags.append(NoveltyFlag(idea_id=idea.id,resembles_id=older.id,
                                         surface_similarity=round(similarity,4)))
    return flags
