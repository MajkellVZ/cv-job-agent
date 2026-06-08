"""RemoteOK adapter — public JSON feed, no API key required.

Great for remote-first candidates. We pull the feed once and filter locally
against the profile's titles/skills.
"""

from __future__ import annotations

import requests

from ..profile import CandidateProfile, Job
from .base import JobSource


class RemoteOKSource(JobSource):
    name = "remoteok"
    URL = "https://remoteok.com/api"

    def search(self, profile: CandidateProfile, limit: int = 25) -> list[Job]:
        try:
            resp = requests.get(
                self.URL, timeout=20,
                headers={"User-Agent": "cv-job-agent (personal job search)"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  [remoteok] feed failed: {exc}")
            return []

        # First element is metadata, skip it.
        postings = [d for d in data if isinstance(d, dict) and d.get("id")]

        terms = {t.lower() for t in profile.target_titles + profile.skills + profile.keywords}
        scored: list[tuple[int, Job]] = []

        for p in postings:
            haystack = " ".join(
                str(p.get(k, "")) for k in ("position", "description", "tags")
            ).lower()
            hits = sum(1 for t in terms if t and t in haystack)
            if hits == 0:
                continue
            scored.append((
                hits,
                Job(
                    source=self.name,
                    title=p.get("position", ""),
                    company=p.get("company", ""),
                    location=p.get("location") or "Remote",
                    url=p.get("url", ""),
                    description=self._clean(p.get("description")),
                    salary=self._salary(p),
                    remote=True,
                    posted=p.get("date", ""),
                    external_id=str(p.get("id", "")),
                ),
            ))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [j for _, j in scored[:limit]]

    @staticmethod
    def _salary(p: dict) -> str:
        lo, hi = p.get("salary_min"), p.get("salary_max")
        if lo and hi:
            return f"{int(lo):,} - {int(hi):,}"
        return ""
