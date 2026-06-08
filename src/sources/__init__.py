"""Registry of available job sources.

`get_sources()` returns the adapters that are actually usable given the current
environment (e.g. Adzuna only if its keys are set, the company source only if
COMPANY_CAREERS / *_BOARDS are set). Add new boards here.
"""

from __future__ import annotations

from .adzuna import AdzunaSource
from .base import JobSource
from .company import CompanyCareersSource
from .remoteok import RemoteOKSource

# Order = the order sources are queried.
ALL_SOURCE_CLASSES = [AdzunaSource, CompanyCareersSource, RemoteOKSource]


def get_sources(only: list[str] | None = None,
                countries: list[str] | None = None) -> list[JobSource]:
    sources: list[JobSource] = []
    for cls in ALL_SOURCE_CLASSES:
        # Adzuna is geography-aware; others ignore the kwarg.
        src = cls(countries=countries) if cls is AdzunaSource else cls()
        if only and src.name not in only:
            continue
        if not src.enabled:
            print(f"  [skip] source '{src.name}' is not configured")
            continue
        sources.append(src)
    return sources


__all__ = ["JobSource", "get_sources", "ALL_SOURCE_CLASSES"]
