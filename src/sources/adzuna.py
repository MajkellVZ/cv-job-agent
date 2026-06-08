"""Adzuna adapter.

Adzuna is a job-search aggregator that legally indexes Indeed and hundreds of
other boards. It has a free developer tier:
    https://developer.adzuna.com/

Set ADZUNA_APP_ID and ADZUNA_APP_KEY in your environment.

Geography: Adzuna is queried per country. The agent passes a list of target
country codes; if that list is empty we sweep every supported country
("around the world").
"""

from __future__ import annotations

import os

import requests

from ..countries import WORLD
from ..profile import CandidateProfile, Job
from .base import JobSource


class AdzunaSource(JobSource):
    name = "adzuna"
    BASE = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self, countries: list[str] | None = None):
        self.app_id = os.environ.get("ADZUNA_APP_ID")
        self.app_key = os.environ.get("ADZUNA_APP_KEY")
        # explicit target countries (resolved ISO codes), or [] meaning worldwide
        self.countries = countries or []
        self.enabled = bool(self.app_id and self.app_key)

    def _target_countries(self) -> list[str]:
        return self.countries if self.countries else WORLD

    def search(self, profile: CandidateProfile, limit: int = 25) -> list[Job]:
        if not self.enabled:
            return []

        target = self._target_countries()
        worldwide = not self.countries
        # Going worldwide multiplies calls by ~19 countries, so trim queries.
        queries = profile.search_queries(max_queries=2 if worldwide else 4)
        # Only pin a city when searching a single country and not remote-only.
        where = ""
        if len(target) == 1 and profile.locations and not profile.remote_ok:
            where = profile.locations[0]

        if worldwide:
            print(f"      [adzuna] no countries set -> searching worldwide "
                  f"({len(target)} countries)")
        else:
            from ..countries import names
            print(f"      [adzuna] countries: {names(target)}")

        jobs: list[Job] = []
        for country in target:
            for query in queries:
                params = {
                    "app_id": self.app_id,
                    "app_key": self.app_key,
                    "results_per_page": min(limit, 50),
                    "what": query,
                    "content-type": "application/json",
                }
                if where:
                    params["where"] = where
                try:
                    resp = requests.get(
                        f"{self.BASE}/{country}/search/1", params=params, timeout=20
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                except (requests.RequestException, ValueError) as exc:
                    print(f"        [adzuna:{country}] '{query}' failed: {exc}")
                    continue

                for item in payload.get("results", []):
                    loc = (item.get("location") or {}).get("display_name", "")
                    jobs.append(Job(
                        source=f"{self.name}:{country}",
                        title=item.get("title", ""),
                        company=(item.get("company") or {}).get("display_name", ""),
                        location=loc,
                        url=item.get("redirect_url", ""),
                        description=self._clean(item.get("description")),
                        salary=self._format_salary(item),
                        remote="remote" in (item.get("title", "") + " " + loc).lower(),
                        posted=item.get("created", ""),
                        external_id=str(item.get("id", "")),
                    ))
        return jobs

    @staticmethod
    def _format_salary(item: dict) -> str:
        lo, hi = item.get("salary_min"), item.get("salary_max")
        if lo and hi:
            return f"{int(lo):,} - {int(hi):,}"
        if lo:
            return f"from {int(lo):,}"
        return ""
