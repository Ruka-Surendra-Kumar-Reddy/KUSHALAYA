"""Matching plugin interface — vertical-specific demand/supply scoring."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User


class MatchingPlugin(Protocol):
    def score_candidates(
        self,
        db: Session,
        elder: Elder,
        caregivers: list[Caregiver],
    ) -> list[dict]:
        ...
    algorithm_version: str

    def recommend(
        self,
        db: Session,
        elder_id: int,
        user: User,
        limit: int,
    ) -> dict:
        """Score supply (workers) for demand (client) and persist a match run."""
        ...
