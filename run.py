#!/usr/bin/env python3
"""Command-line entry point for the CV job-search agent (local models via Ollama).

Usage:
    python run.py path/to/cv.pdf
    python run.py cv.pdf --model qwen2.5 --min-score 70 --sources adzuna,remoteok
"""

from __future__ import annotations

import argparse
import os
import sys

from src import JobAgent, save_reports
from src.llm import LLMError


def main() -> int:
    ap = argparse.ArgumentParser(description="Find open jobs that match a CV, using a local LLM.")
    ap.add_argument("cv", help="Path to the CV file (.pdf, .docx, .txt)")
    ap.add_argument("--min-score", type=int, default=0,
                    help="Drop matches below this fit score (0-100)")
    ap.add_argument("--sources", default="",
                    help="Comma-separated subset, e.g. adzuna,remoteok")
    ap.add_argument("--model", default=None,
                    help="Ollama model name (default: $OLLAMA_MODEL or llama3.1)")
    ap.add_argument("--ollama-host", default=None,
                    help="Ollama server URL (default: $OLLAMA_HOST or http://localhost:11434)")
    ap.add_argument("--countries", default=None,
                    help="Comma-separated countries to search (codes or names, "
                         "e.g. us,gb,de or 'United States,Germany'). "
                         "Omit to search worldwide. Env: JOB_COUNTRIES")
    ap.add_argument("--limit", type=int, default=25,
                    help="Max results requested per source")
    ap.add_argument("--out", default="output", help="Output directory")
    args = ap.parse_args()

    only = [s.strip() for s in args.sources.split(",") if s.strip()] or None

    countries_raw = args.countries if args.countries is not None else os.environ.get("JOB_COUNTRIES", "")
    countries = [c.strip() for c in countries_raw.split(",") if c.strip()] or None

    agent = JobAgent(model=args.model, ollama_host=args.ollama_host,
                     sources_only=only, per_source_limit=args.limit,
                     countries=countries)
    try:
        result = agent.run(args.cv, min_score=args.min_score)
    except LLMError as exc:
        print(f"\nLocal model error: {exc}", file=sys.stderr)
        return 2

    csv_path, html_path = save_reports(result, out_dir=args.out)

    print("\nTop matches:")
    for j in result.jobs[:10]:
        print(f"  {j.score:>3}  {j.title[:45]:<45}  {j.company[:25]:<25}  [{j.source}]")
    print(f"\nReports written:\n  {csv_path}\n  {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
