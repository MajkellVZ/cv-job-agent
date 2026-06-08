"""Applicant-Tracking-System (ATS) providers + auto-detection.

Most company career pages are powered by one of a handful of ATS vendors, each
of which exposes a public JSON endpoint intended for embedding job boards. This
module provides:

  * a pure fetcher per provider:  fetch_<provider>(token, query) -> list[Job]
  * a PROVIDERS registry
  * detect_ats(url) -> (provider, token)   # sniffs a careers page for its ATS

These are public, embed-intended endpoints — no scraping, no keys. Be polite:
the company source rate-limits and sets a clear User-Agent.
"""

from __future__ import annotations

import re

import requests

from ..profile import CandidateProfile, Job

UA = {"User-Agent": "cv-job-agent (personal job search; +https://ollama.com)"}
TIMEOUT = 20


def matches(profile: CandidateProfile, *texts: str) -> int:
    """Count how many profile terms appear in the given texts (lenient filter)."""
    terms = {t.lower() for t in profile.target_titles + profile.skills + profile.keywords}
    hay = " ".join(texts).lower()
    return sum(1 for t in terms if t and t in hay)


def _clean(text: str | None, max_len: int = 1500) -> str:
    if not text:
        return ""
    # strip HTML tags cheaply
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text[:max_len]


# --------------------------------------------------------------------------- #
# Provider fetchers — each returns ALL current postings (filtering is upstream)
# --------------------------------------------------------------------------- #

def fetch_greenhouse(token: str, query: str = "") -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    data = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for j in data.get("jobs", []):
        out.append(Job(
            source=f"greenhouse:{token}", title=j.get("title", ""), company=token,
            location=(j.get("location") or {}).get("name", ""),
            url=j.get("absolute_url", ""), description=_clean(j.get("content", "")),
            posted=j.get("updated_at", ""), external_id=str(j.get("id", "")),
        ))
    return out


def fetch_lever(token: str, query: str = "") -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    data = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for p in data:
        cats = p.get("categories", {}) or {}
        out.append(Job(
            source=f"lever:{token}", title=p.get("text", ""), company=token,
            location=cats.get("location", ""), url=p.get("hostedUrl", ""),
            description=_clean(p.get("descriptionPlain") or p.get("description", "")),
            remote="remote" in str(cats).lower(),
            posted=str(p.get("createdAt", "")), external_id=str(p.get("id", "")),
        ))
    return out


def fetch_ashby(token: str, query: str = "") -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
    data = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for j in data.get("jobs", []):
        out.append(Job(
            source=f"ashby:{token}", title=j.get("title", ""), company=token,
            location=j.get("location", ""),
            url=j.get("jobUrl") or j.get("applyUrl", ""),
            description=_clean(j.get("descriptionPlain") or j.get("description", "")),
            remote=bool(j.get("isRemote")),
            posted=j.get("publishedAt", ""), external_id=str(j.get("id", "")),
        ))
    return out


def fetch_smartrecruiters(token: str, query: str = "") -> list[Job]:
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100"
    data = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for p in data.get("content", []):
        loc = p.get("location", {}) or {}
        city = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
        pid = p.get("id", "")
        out.append(Job(
            source=f"smartrecruiters:{token}", title=p.get("name", ""), company=token,
            location=city, url=f"https://jobs.smartrecruiters.com/{token}/{pid}",
            remote=bool(loc.get("remote")),
            posted=p.get("releasedDate", ""), external_id=str(pid),
        ))
    return out


def fetch_recruitee(token: str, query: str = "") -> list[Job]:
    url = f"https://{token}.recruitee.com/api/offers/"
    data = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for o in data.get("offers", []):
        out.append(Job(
            source=f"recruitee:{token}", title=o.get("title", ""), company=token,
            location=o.get("location", ""),
            url=o.get("careers_url") or o.get("careers_apply_url", ""),
            description=_clean(o.get("description", "")),
            remote="remote" in (o.get("location", "") or "").lower(),
            posted=o.get("published_at", ""), external_id=str(o.get("id", "")),
        ))
    return out


def fetch_workable(token: str, query: str = "") -> list[Job]:
    url = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
    body = {"query": query or "", "location": [], "department": [],
            "worktype": [], "remote": [], "limit": 100}
    data = requests.post(url, json=body, headers=UA, timeout=TIMEOUT).json()
    out = []
    for r in data.get("results", []):
        loc = r.get("location", {}) or {}
        city = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
        code = r.get("shortcode", "")
        out.append(Job(
            source=f"workable:{token}", title=r.get("title", ""), company=token,
            location=city or ("Remote" if r.get("remote") else ""),
            url=f"https://apply.workable.com/{token}/j/{code}/",
            remote=bool(r.get("remote")),
            posted=r.get("published_on", ""), external_id=str(code),
        ))
    return out


def fetch_workday(token: str, query: str = "") -> list[Job]:
    """Best-effort: token is 'tenant|dc|site' from detect_ats (Workday is fiddly)."""
    try:
        tenant, dc, site = token.split("|")
    except ValueError:
        return []
    url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query or ""}
    data = requests.post(url, json=body, headers=UA, timeout=TIMEOUT).json()
    base = f"https://{tenant}.{dc}.myworkdayjobs.com/{site}"
    out = []
    for p in data.get("jobPostings", []):
        path = p.get("externalPath", "")
        out.append(Job(
            source=f"workday:{tenant}", title=p.get("title", ""), company=tenant,
            location=p.get("locationsText", ""), url=base + path,
            posted=p.get("postedOn", ""), external_id=path,
        ))
    return out


PROVIDERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "recruitee": fetch_recruitee,
    "workable": fetch_workable,
    "workday": fetch_workday,
}


# --------------------------------------------------------------------------- #
# Auto-detection: sniff a careers page (final URL + HTML) for its ATS
# --------------------------------------------------------------------------- #

# (provider, regex) — regex's first group is the token. Ordered most-specific first.
_SIGNATURES: list[tuple[str, re.Pattern]] = [
    ("greenhouse", re.compile(r"boards(?:-api)?\.greenhouse\.io/(?:embed/job_board\?for=|v1/boards/)?([\w-]+)")),
    ("greenhouse", re.compile(r"greenhouse\.io/embed/job_board\?for=([\w-]+)")),
    ("lever", re.compile(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([\w-]+)")),
    ("ashby", re.compile(r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([\w-]+)")),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)")),
    ("smartrecruiters", re.compile(r"api\.smartrecruiters\.com/v1/companies/([\w-]+)")),
    ("recruitee", re.compile(r"([\w-]+)\.recruitee\.com")),
    ("workable", re.compile(r"apply\.workable\.com/([\w-]+)")),
    ("workable", re.compile(r"([\w-]+)\.workable\.com")),
]

_WORKDAY = re.compile(r"([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[\w-]+/)?([\w-]+)")


def detect_ats(url: str) -> tuple[str | None, str | None]:
    """Fetch a careers URL and identify the ATS + board token behind it."""
    try:
        resp = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        blob = f"{resp.url}\n{resp.text[:200000]}"
    except requests.RequestException:
        blob = url  # fall back to sniffing just the URL string

    wd = _WORKDAY.search(blob)
    if wd:
        tenant, dc, site = wd.group(1), wd.group(2), wd.group(3)
        return "workday", f"{tenant}|{dc}|{site}"

    for provider, pat in _SIGNATURES:
        m = pat.search(blob)
        if m:
            return provider, m.group(1)
    return None, None
