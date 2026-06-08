"""Write the ranked results to CSV and a self-contained HTML report."""

from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path

from .profile import CandidateProfile, Job


def write_csv(jobs: list[Job], path: str) -> None:
    fields = ["score", "title", "company", "location", "salary",
              "remote", "source", "url", "reasons", "posted"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for j in jobs:
            w.writerow(j.to_dict())


def _badge(score: int | None) -> str:
    s = score or 0
    color = "#16a34a" if s >= 80 else "#ca8a04" if s >= 60 else "#dc2626"
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:6px;font-weight:600">{s}</span>'


def write_html(profile: CandidateProfile, jobs: list[Job], path: str) -> None:
    rows = []
    for j in jobs:
        rows.append(f"""
        <tr>
          <td style="text-align:center">{_badge(j.score)}</td>
          <td><a href="{html.escape(j.url)}" target="_blank" rel="noopener">{html.escape(j.title)}</a>
              <div class="muted">{html.escape(j.source)}</div></td>
          <td>{html.escape(j.company)}</td>
          <td>{html.escape(j.location)}{' · remote' if j.remote else ''}</td>
          <td>{html.escape(j.salary)}</td>
          <td class="muted">{html.escape(j.reasons)}</td>
        </tr>""")

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job matches — {html.escape(profile.full_name or 'candidate')}</title>
<style>
  body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f8fafc;color:#0f172a}}
  .wrap{{max-width:1000px;margin:0 auto;padding:32px 20px}}
  h1{{margin:0 0 4px}}
  .sub{{color:#64748b;margin-bottom:24px}}
  .chips span{{display:inline-block;background:#e2e8f0;border-radius:999px;padding:3px 10px;margin:2px;font-size:13px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  th,td{{padding:12px 14px;text-align:left;border-bottom:1px solid #f1f5f9;vertical-align:top;font-size:14px}}
  th{{background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#475569}}
  a{{color:#2563eb;text-decoration:none;font-weight:600}} a:hover{{text-decoration:underline}}
  .muted{{color:#94a3b8;font-size:12px}}
</style></head><body><div class="wrap">
  <h1>{html.escape(profile.headline or 'Job matches')}</h1>
  <div class="sub">{html.escape(profile.full_name)} · {len(jobs)} ranked openings ·
       generated {datetime.now():%Y-%m-%d %H:%M}</div>
  <div class="chips">{''.join(f'<span>{html.escape(s)}</span>' for s in profile.skills[:18])}</div>
  <table>
    <thead><tr><th>Fit</th><th>Role</th><th>Company</th><th>Location</th><th>Salary</th><th>Why</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div></body></html>"""
    Path(path).write_text(doc, encoding="utf-8")
