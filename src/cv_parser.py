"""Read a CV file (PDF / DOCX / TXT) and turn it into a CandidateProfile.

Text extraction is done locally; the *structuring* step uses a local LLM
(via Ollama) so the profile is robust to messy CV layouts and nothing leaves
your machine.
"""

from __future__ import annotations

from pathlib import Path

from .llm import LocalLLM, loads_json
from .profile import CandidateProfile

# --------------------------------------------------------------------------- #
# 1. Local text extraction
# --------------------------------------------------------------------------- #

def extract_text(cv_path: str) -> str:
    path = Path(cv_path)
    if not path.exists():
        raise FileNotFoundError(f"CV not found: {cv_path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in (".docx", ".doc"):
        return _extract_docx(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported CV format: {suffix} (use pdf, docx, txt)")


def _extract_pdf(path: Path) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _extract_docx(path: Path) -> str:
    import docx
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs).strip()


# --------------------------------------------------------------------------- #
# 2. Structure the text into a CandidateProfile (local LLM)
# --------------------------------------------------------------------------- #

_PROFILE_SCHEMA_PROMPT = """You are a precise CV parser. Read the CV text and return ONLY a JSON object \
(no markdown, no commentary) with these fields:

{
  "full_name": string,
  "headline": string,                 // best one-line role description
  "seniority": string,                // one of: intern, junior, mid, senior, lead, manager, director, executive
  "years_experience": number,         // total professional years, estimate if needed
  "target_titles": string[],          // 2-5 realistic job titles this person should apply for
  "skills": string[],                 // concrete hard skills, tools, languages (max 25)
  "industries": string[],             // industries they have worked in
  "locations": string[],              // city/country the candidate lists; empty if none
  "remote_ok": boolean,               // true unless the CV strongly implies on-site only
  "summary": string,                  // 2-3 sentence neutral summary of the candidate
  "keywords": string[]                // extra search keywords useful for job boards (max 15)
}

Infer sensibly when something is implicit. Never invent employers or degrees."""


def build_profile(cv_text: str, llm: LocalLLM | None = None) -> CandidateProfile:
    llm = llm or LocalLLM()

    # Keep token use sane on very long CVs.
    trimmed = cv_text[:20000]

    raw = llm.chat(
        system=_PROFILE_SCHEMA_PROMPT,
        user=f"CV TEXT:\n\n{trimmed}",
        json_mode=True,
        max_tokens=1500,
    )
    data = loads_json(raw)
    if not isinstance(data, dict):
        raise ValueError("CV parser did not return a JSON object")

    return CandidateProfile(
        full_name=data.get("full_name", ""),
        headline=data.get("headline", ""),
        seniority=data.get("seniority", ""),
        years_experience=data.get("years_experience"),
        target_titles=list(data.get("target_titles", []) or []),
        skills=list(data.get("skills", []) or []),
        industries=list(data.get("industries", []) or []),
        locations=list(data.get("locations", []) or []),
        remote_ok=bool(data.get("remote_ok", True)),
        summary=data.get("summary", ""),
        keywords=list(data.get("keywords", []) or []),
    )


def profile_from_cv(cv_path: str, llm: LocalLLM | None = None) -> CandidateProfile:
    return build_profile(extract_text(cv_path), llm=llm)
