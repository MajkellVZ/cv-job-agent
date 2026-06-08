"""Source adapter interface.

A *source* knows how to query one job provider and return normalized Job objects.
Add a new board by subclassing JobSource and dropping it into the registry in
sources/__init__.py — nothing else in the agent needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..profile import CandidateProfile, Job


class JobSource(ABC):
    #: short stable identifier, e.g. "adzuna"
    name: str = "base"

    #: set False if the adapter needs credentials that aren't configured
    enabled: bool = True

    @abstractmethod
    def search(self, profile: CandidateProfile, limit: int = 25) -> list[Job]:
        """Return up to `limit` jobs relevant to the profile."""
        raise NotImplementedError

    # small shared helper
    @staticmethod
    def _clean(text: str | None, max_len: int = 1500) -> str:
        if not text:
            return ""
        text = " ".join(text.split())
        return text[:max_len]
