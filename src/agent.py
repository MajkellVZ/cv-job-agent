"""The agent: CV in, ranked opportunities out — powered by a local LLM (Ollama).

Pipeline:
    parse CV -> CandidateProfile
    fan out to every configured source
    de-duplicate
    local-LLM-score against the profile
    write CSV + HTML report
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .cv_parser import profile_from_cv
from .countries import names, resolve_countries
from .llm import LocalLLM
from .matcher import score_jobs
from .profile import CandidateProfile, Job
from .report import write_csv, write_html
from .sources import get_sources


@dataclass
class AgentResult:
    profile: CandidateProfile
    jobs: list[Job]


class JobAgent:
    def __init__(self, model: str | None = None, ollama_host: str | None = None,
                 sources_only: list[str] | None = None,
                 per_source_limit: int = 25,
                 countries: list[str] | None = None):
        self.llm = LocalLLM(model=model, host=ollama_host)
        self.sources_only = sources_only
        self.per_source_limit = per_source_limit
        self.countries, unknown = resolve_countries(countries)
        if unknown:
            print(f"      [countries] ignoring unrecognized: {', '.join(unknown)}")

    def run(self, cv_path: str, min_score: int = 0) -> AgentResult:
        print(f"[0/4] Using local model '{self.llm.model}' at {self.llm.host}")
        self.llm.health_check()

        print(f"[1/4] Reading CV: {cv_path}")
        profile = profile_from_cv(cv_path, llm=self.llm)
        print(f"      -> {profile.headline or '(no headline)'} "
              f"| targets: {', '.join(profile.target_titles) or 'n/a'}")

        print("[2/4] Searching sources...")
        if self.countries:
            print(f"      geography: {names(self.countries)}")
        else:
            print("      geography: worldwide (no countries specified)")
        sources = get_sources(self.sources_only, countries=self.countries)
        if not sources:
            print("      no usable sources — set ADZUNA_APP_ID/KEY or board env vars")
        collected: list[Job] = []
        for src in sources:
            found = src.search(profile, limit=self.per_source_limit)
            print(f"      {src.name}: {len(found)} found")
            collected.extend(found)

        jobs = self._dedupe(collected)
        print(f"      {len(jobs)} unique jobs after de-duplication")

        print("[3/4] Scoring matches (local LLM)...")
        jobs = score_jobs(profile, jobs, llm=self.llm)
        if min_score:
            jobs = [j for j in jobs if (j.score or 0) >= min_score]

        print(f"[4/4] Done — {len(jobs)} ranked opportunities")
        return AgentResult(profile=profile, jobs=jobs)

    @staticmethod
    def _dedupe(jobs: list[Job]) -> list[Job]:
        seen, out = set(), []
        for j in jobs:
            k = j.dedup_key()
            if k in seen:
                continue
            seen.add(k)
            out.append(j)
        return out


def save_reports(result: AgentResult, out_dir: str = "output") -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "matches.csv")
    html_path = os.path.join(out_dir, "matches.html")
    write_csv(result.jobs, csv_path)
    write_html(result.profile, result.jobs, html_path)
    return csv_path, html_path
