"""Search specific companies' careers pages.

You give it a list of companies (env var COMPANY_CAREERS, comma-separated). Each
entry is one of:

  greenhouse:stripe        provider + board token (fastest, most reliable)
  lever:netflix
  ashby:ramp
  https://www.acme.com/careers   a careers URL -> the ATS is auto-detected
  https://jobs.lever.co/figma    a direct ATS board URL

For URLs that aren't on a recognized ATS, it falls back to a generic HTML
scrape (best-effort; JS-heavy single-page sites may return little — see the
optional render step below).

Back-compat: GREENHOUSE_BOARDS / LEVER_BOARDS still work and are merged in.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import requests

from ..profile import CandidateProfile, Job
from .ats import PROVIDERS, UA, TIMEOUT, detect_ats, matches, _clean
from .base import JobSource

_JOBLIKE = ("/job", "/jobs/", "/career", "/careers/", "/position", "/opening",
            "/vacancy", "/vacancies", "/apply", "greenhouse.io", "lever.co",
            "ashbyhq.com", "smartrecruiters.com", "workable.com", "recruitee.com")


class CompanyCareersSource(JobSource):
    name = "company"

    def __init__(self):
        self.companies = self._collect_companies()
        self.render = os.environ.get("CAREERS_RENDER", "").strip() in ("1", "true", "yes")
        self.enabled = bool(self.companies)

    @staticmethod
    def _collect_companies() -> list[str]:
        entries: list[str] = []
        raw = os.environ.get("COMPANY_CAREERS", "")
        entries += [e.strip() for e in raw.split(",") if e.strip()]
        # back-compat with the old per-provider vars
        for prov, var in (("greenhouse", "GREENHOUSE_BOARDS"), ("lever", "LEVER_BOARDS")):
            for tok in os.environ.get(var, "").split(","):
                tok = tok.strip()
                if tok:
                    entries.append(f"{prov}:{tok}")
        # de-dupe, keep order
        seen, out = set(), []
        for e in entries:
            if e not in seen:
                seen.add(e)
                out.append(e)
        return out

    def search(self, profile: CandidateProfile, limit: int = 25) -> list[Job]:
        query = (profile.target_titles or [profile.headline or ""])[0]
        results: list[Job] = []

        for entry in self.companies:
            try:
                jobs = self._fetch_one(entry, query)
            except requests.RequestException as exc:
                print(f"  [company] '{entry}' failed: {exc}")
                jobs = []
            except Exception as exc:  # noqa: BLE001 - one bad company shouldn't kill the run
                print(f"  [company] '{entry}' error: {exc}")
                jobs = []

            # keep only postings relevant to the profile
            relevant = [j for j in jobs if matches(profile, j.title, j.description) > 0]
            print(f"  [company] {entry}: {len(jobs)} posted, {len(relevant)} relevant")
            results.extend(relevant)
            time.sleep(0.4)  # be polite between companies

        return results[:limit] if limit else results

    # ------------------------------------------------------------------ #

    def _fetch_one(self, entry: str, query: str) -> list[Job]:
        # 1. explicit provider:token
        if ":" in entry and not entry.lower().startswith(("http://", "https://")):
            provider, token = entry.split(":", 1)
            provider = provider.strip().lower()
            if provider in PROVIDERS:
                return PROVIDERS[provider](token.strip(), query)

        # 2. a URL — detect the ATS, else generic fallback
        url = entry if entry.lower().startswith(("http://", "https://")) else f"https://{entry}"
        provider, token = detect_ats(url)
        if provider and token:
            print(f"  [company] detected {provider} board '{token}' for {url}")
            return PROVIDERS[provider](token, query)

        print(f"  [company] no known ATS for {url} — generic scrape")
        return self._generic_scrape(url)

    # ------------------------------------------------------------------ #

    def _generic_scrape(self, url: str) -> list[Job]:
        if not self._robots_allow(url):
            print(f"  [company] robots.txt disallows {url}; skipping")
            return []

        html = self._render(url) if self.render else None
        if html is None:
            resp = requests.get(url, headers=UA, timeout=TIMEOUT)
            resp.raise_for_status()
            html = resp.text

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("  [company] install beautifulsoup4 for generic scraping")
            return []

        soup = BeautifulSoup(html, "html.parser")
        domain = urlparse(url).netloc
        seen, out = set(), []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = " ".join(a.get_text().split())
            low = href.lower()
            if not any(k in low for k in _JOBLIKE):
                continue
            if not text or len(text) < 3 or len(text) > 120:
                continue
            full = urljoin(url, href)
            if full in seen:
                continue
            seen.add(full)
            out.append(Job(
                source=f"company:{domain}", title=text, company=domain,
                url=full, description="",
            ))
        if not out:
            print("  [company] generic scrape found nothing (page may be JS-rendered; "
                  "set CAREERS_RENDER=1 with Playwright installed)")
        return out

    @staticmethod
    def _render(url: str) -> str | None:
        """Optional JS rendering via Playwright, only if installed + enabled."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("  [company] CAREERS_RENDER set but Playwright not installed "
                  "(`pip install playwright && playwright install chromium`)")
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(user_agent=UA["User-Agent"])
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
                browser.close()
                return html
        except Exception as exc:  # noqa: BLE001
            print(f"  [company] render failed: {exc}")
            return None

    @staticmethod
    def _robots_allow(url: str) -> bool:
        try:
            parts = urlparse(url)
            rp = robotparser.RobotFileParser()
            rp.set_url(f"{parts.scheme}://{parts.netloc}/robots.txt")
            rp.read()
            return rp.can_fetch(UA["User-Agent"], url)
        except Exception:  # noqa: BLE001 - if robots can't be read, proceed politely
            return True
