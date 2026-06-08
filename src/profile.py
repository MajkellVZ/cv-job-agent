"""Core data models for the agent: the candidate profile and a normalized Job."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CandidateProfile:
    """A structured view of the candidate, extracted from their CV.

    This is what the agent searches *with*. Sources turn it into queries,
    and the matcher scores jobs *against* it.
    """

    full_name: str = ""
    headline: str = ""                      # e.g. "Senior Backend Engineer"
    seniority: str = ""                     # junior | mid | senior | lead | director ...
    years_experience: Optional[float] = None
    target_titles: list[str] = field(default_factory=list)   # roles to search for
    skills: list[str] = field(default_factory=list)          # hard skills / tools
    industries: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)       # preferred locations
    remote_ok: bool = True
    summary: str = ""                       # short free-text summary of the candidate
    keywords: list[str] = field(default_factory=list)        # extra search keywords

    def to_dict(self) -> dict:
        return asdict(self)

    def search_queries(self, max_queries: int = 4) -> list[str]:
        """Turn the profile into a handful of distinct search query strings."""
        queries: list[str] = []
        for t in self.target_titles:
            queries.append(t)
        if not queries and self.headline:
            queries.append(self.headline)
        # de-duplicate while preserving order
        seen, out = set(), []
        for q in queries:
            k = q.lower().strip()
            if k and k not in seen:
                seen.add(k)
                out.append(q)
        return out[:max_queries] or ["software engineer"]


@dataclass
class Job:
    """A normalized job posting, regardless of which source it came from."""

    source: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    salary: str = ""
    remote: bool = False
    posted: str = ""                 # ISO date string if available
    external_id: str = ""            # source-native id for de-duplication

    # Filled in by the matcher
    score: Optional[int] = None      # 0-100 fit score
    reasons: str = ""                # why it matched / gaps

    def dedup_key(self) -> str:
        if self.external_id:
            return f"{self.source}:{self.external_id}"
        return f"{self.company.lower().strip()}|{self.title.lower().strip()}"

    def to_dict(self) -> dict:
        return asdict(self)
