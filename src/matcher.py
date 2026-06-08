"""Score and rank jobs against the candidate profile, using a local LLM.

Two stages:
  1. cheap local keyword pre-filter to drop obvious mismatches and cap volume
  2. local-LLM scoring in batches -> 0-100 fit score + a short reason per job
"""

from __future__ import annotations

import json

from .llm import LocalLLM, loads_json
from .profile import CandidateProfile, Job

_SCORER_SYSTEM = """You are a sharp technical recruiter. Given a candidate profile and a batch of \
job postings, score how well each job fits the candidate.

Return ONLY a JSON object (no markdown) of the form:
  {"scores": [{"id": <int index of the job>, "score": <0-100>, "reason": "<=25 words: fit + biggest gap"}]}

Scoring guidance:
  90-100  strong match on title, seniority, and core skills
  70-89   good match, minor gaps
  50-69   plausible stretch or partial overlap
  <50     weak fit (wrong level, domain, or missing core skills)
Be honest and calibrated. Do not inflate scores."""


def _prefilter(profile: CandidateProfile, jobs: list[Job], cap: int) -> list[Job]:
    terms = {t.lower() for t in profile.target_titles + profile.skills + profile.keywords}
    scored = []
    for j in jobs:
        hay = f"{j.title} {j.description}".lower()
        hits = sum(1 for t in terms if t and t in hay)
        scored.append((hits, j))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [j for _, j in scored[:cap]]


def score_jobs(profile: CandidateProfile, jobs: list[Job],
               llm: LocalLLM | None = None, batch_size: int = 6,
               max_to_score: int = 60) -> list[Job]:
    if not jobs:
        return []
    llm = llm or LocalLLM()

    jobs = _prefilter(profile, jobs, max_to_score)

    profile_blob = json.dumps({
        "headline": profile.headline,
        "seniority": profile.seniority,
        "years_experience": profile.years_experience,
        "target_titles": profile.target_titles,
        "skills": profile.skills,
        "industries": profile.industries,
        "summary": profile.summary,
    }, ensure_ascii=False)

    for start in range(0, len(jobs), batch_size):
        batch = jobs[start : start + batch_size]
        listing = []
        for i, j in enumerate(batch):
            listing.append(
                f'#{i} TITLE: {j.title} | COMPANY: {j.company} | '
                f'LOCATION: {j.location}\nDESC: {j.description[:700]}'
            )
        user = (
            f"CANDIDATE PROFILE:\n{profile_blob}\n\n"
            f"JOBS (score each by its #):\n\n" + "\n\n".join(listing)
        )
        try:
            raw = llm.chat(system=_SCORER_SYSTEM, user=user,
                           json_mode=True, max_tokens=1200)
            results = _parse_scores(raw)
        except Exception as exc:  # noqa: BLE001 - keep the run alive
            print(f"  [matcher] batch failed: {exc}")
            results = []

        for r in results:
            idx = r.get("id")
            if isinstance(idx, int) and 0 <= idx < len(batch):
                try:
                    batch[idx].score = int(r.get("score", 0))
                except (TypeError, ValueError):
                    batch[idx].score = 0
                batch[idx].reasons = str(r.get("reason", ""))

    # unscored jobs get 0 so they sort last
    for j in jobs:
        if j.score is None:
            j.score = 0
    jobs.sort(key=lambda j: j.score or 0, reverse=True)
    return jobs


def _parse_scores(text: str) -> list[dict]:
    data = loads_json(text)
    if isinstance(data, dict):
        data = data.get("scores") or data.get("results") or []
    return data if isinstance(data, list) else []
