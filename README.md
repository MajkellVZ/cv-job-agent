# CV Job Agent (local models)

An agent that reads your **CV** and finds **open job opportunities** that match it,
across multiple job sites, then ranks them by fit and writes a clean report.
All the AI runs **locally via [Ollama](https://ollama.com)** — no API keys, no
cloud calls, your CV never leaves your machine.

```
CV (pdf/docx/txt)  ──▶  profile  ──▶  search many sources  ──▶  rank by fit  ──▶  report (CSV + HTML)
                         (local LLM)                            (local LLM)
```

## What it does

1. **Reads your CV** (PDF, DOCX, or TXT) and extracts a structured profile —
   target titles, skills, seniority, location — using a local model.
2. **Searches several job sources** through a pluggable adapter layer.
3. **De-duplicates** listings that appear on more than one source.
4. **Scores every job 0–100** against your profile and explains the fit/gap,
   again with the local model.
5. **Writes `matches.csv` and a shareable `matches.html`** ranked best-first.

## A note on Indeed

Scraping Indeed directly violates its Terms of Service and is actively blocked
(bot protection, login walls), so a raw scraper would break constantly. Instead
this agent uses **[Adzuna](https://developer.adzuna.com/)**, a job aggregator
that legally indexes Indeed *and* hundreds of other boards, via its free API.

## Sources included

| Source       | Coverage                                        | Key needed |
|--------------|-------------------------------------------------|------------|
| **Adzuna**   | Indeed + hundreds of boards (aggregator)        | Free key   |
| **Company careers** | Any company's careers page (see below)   | None       |
| **RemoteOK** | Remote roles                                    | None       |

So you get both halves: **broad sites like Indeed** (via the Adzuna aggregator)
**and** the **careers page of any specific company** you care about.

### Searching a specific company's careers page

Set `COMPANY_CAREERS` to a comma-separated list. Each entry is either an explicit
`provider:token` or just a careers URL — the agent auto-detects which applicant
tracking system (ATS) powers the page and calls its public job API:

```
COMPANY_CAREERS=greenhouse:stripe,lever:netflix,https://www.acme.com/careers
```

Auto-detected ATS providers: **Greenhouse, Lever, Ashby, SmartRecruiters,
Recruitee, Workable, Workday**. The `token` for `provider:token` is the company
slug in its board URL (e.g. `boards.greenhouse.io/stripe` → `stripe`).

For a careers page that isn't on a recognized ATS, the agent falls back to a
**generic HTML scrape** that extracts job links. Many modern career sites are
JavaScript-rendered, so the plain scrape may find little — in that case install
Playwright and set `CAREERS_RENDER=1` to render the page first:

```bash
pip install playwright && playwright install chromium
export CAREERS_RENDER=1
```

### Geography: certain countries, or worldwide

By default the agent searches **worldwide** — Adzuna is queried across every
country it supports. To restrict to certain countries, pass `--countries` (or set
`JOB_COUNTRIES`); accepts ISO codes or names:

```bash
python run.py cv.pdf --countries us,gb,de
python run.py cv.pdf --countries "United States,Germany"
# no flag -> worldwide
```

Supported: United Kingdom, United States, Austria, Australia, Belgium, Brazil,
Canada, Switzerland, Germany, Spain, France, India, Italy, Mexico, Netherlands,
New Zealand, Poland, Singapore, South Africa. Unrecognized inputs are ignored
with a warning. (Worldwide multiplies API calls per country, so the agent trims
to your top 2 search terms in that mode to stay within Adzuna's free rate limit;
explicit countries use up to 4 terms. RemoteOK and company-careers sources are
location-agnostic and run regardless.)

## Setup

### 1. Install and start Ollama
```bash
# Install from https://ollama.com, then pull a model:
ollama pull llama3.1          # ~4.7 GB; good default
# alternatives: qwen2.5, mistral, gemma2, llama3.2 (smaller/faster)
ollama serve                  # usually already running after install
```
Pick a model that fits your RAM/VRAM. 7–8B models (llama3.1, qwen2.5) give the
best parsing/scoring quality; 3B models (llama3.2) are faster on modest hardware.

### 2. Install the agent
```bash
pip install -r requirements.txt
cp .env.example .env          # adjust model + add Adzuna keys
export $(grep -v '^#' .env | xargs)   # or use direnv / python-dotenv
```

Config:
- `OLLAMA_MODEL` / `OLLAMA_HOST` — which local model and server to use.
- `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` — recommended; free at developer.adzuna.com.
- `GREENHOUSE_BOARDS` / `LEVER_BOARDS` — optional, comma-separated company tokens
  (the slug in a company's job-board URL, e.g. `boards.greenhouse.io/stripe` → `stripe`).

## Usage

```bash
python run.py path/to/cv.pdf
python run.py cv.pdf --countries us,gb --min-score 70
python run.py cv.pdf --model qwen2.5 --sources adzuna,company --limit 40
# no --countries -> worldwide
```

Or from Python:

```python
from cv_job_agent import JobAgent, save_reports

agent = JobAgent(model="llama3.1", per_source_limit=30)
result = agent.run("cv.pdf", min_score=60)
save_reports(result, out_dir="output")
```

## Architecture

```
cv_job_agent/
  llm.py            LocalLLM — talks to the Ollama HTTP API (JSON mode, health check)
  profile.py        CandidateProfile + Job data models
  cv_parser.py      extract text → structured profile (local LLM)
  sources/
    base.py         JobSource interface
    adzuna.py       Adzuna adapter (Indeed + many boards)
    company.py      Company careers: ATS auto-detect + generic HTML fallback
    ats.py          ATS providers (Greenhouse/Lever/Ashby/SmartRecruiters/
                    Recruitee/Workable/Workday) + detect_ats()
    remoteok.py     RemoteOK adapter
    __init__.py     source registry (only enables configured sources)
  matcher.py        keyword pre-filter → local-LLM scoring in batches
  report.py         CSV + HTML output
  agent.py          orchestrates the whole pipeline
run.py              CLI
```

## Swapping the model backend

Everything goes through `cv_job_agent/llm.py`. To use a different local runtime
(LM Studio, llama.cpp server, vLLM, an OpenAI-compatible endpoint), implement a
class with the same `chat(system, user, json_mode, max_tokens) -> str` method and
pass it where `LocalLLM` is constructed. Ollama also exposes an OpenAI-compatible
endpoint at `/v1/chat/completions` if you prefer that shape.

## Notes & limits

- Local scoring speed depends on your hardware and model size; lower `--limit` and
  `max_to_score` (in `matcher.py`) if runs feel slow. Batch size is 6 by default.
- Smaller models occasionally return imperfect JSON; the parser is lenient and the
  scorer skips any batch it can't read rather than crashing.
- Respect each source's rate limits and terms; this is built for *personal* job search.
- The agent never auto-applies; it surfaces ranked opportunities for you to review.
