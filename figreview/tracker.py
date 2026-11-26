"""Run the review for every figure in a manifest and write the tracker + feedback drafts.

    python -m figreview manifest.yaml --today 2026-11-25
"""
import argparse
import csv
import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from .checks import review_figure

SEVERITY_ORDER = {"blocker": 0, "question": 1, "note": 2}


def suggested_status(findings):
    sev = {f.severity for f in findings}
    if "blocker" in sev:
        return "needs_changes"
    if "question" in sev:
        return "waiting_on_answer"
    return "approved"


def needs_follow_up(entry, status, today, after_days):
    if status == "approved":
        return None
    days = (today - entry["last_contact"]).days
    if days >= after_days:
        return f"No reply in {days} days"
    if (entry["due"] - today).days <= 2:
        return f"Due {entry['due']:%b %d}"
    return None


def _n(k, word):
    return f"{k} {word}" + ("" if k == 1 else "s")


def draft_feedback(entry, fig, number, findings, reviewer, today):
    first = entry["owner"].split()[0]
    title = fig.get("title") or entry["id"]
    reply_by = min(entry["due"] - timedelta(days=1), today + timedelta(days=2))
    if not findings:
        return (f"Subject: Figure {number} approved: {title}\n\nHi {first},\n\n"
                f"I checked \"{title}\" against {entry['source']}. Every plotted value, the caption numbers "
                f"and the written claims match the data, and the labels have units. I've marked it approved.\n\n"
                f"Thanks,\n{reviewer}\n")
    blockers = sum(f.severity == "blocker" for f in findings)
    lines = [f"Subject: Figure {number} review: {_n(len(findings), 'item')} before sign-off ({title})", "",
             f"Hi {first},", "",
             f"I checked \"{title}\" against {entry['source']}. "
             + (f"{_n(blockers, 'item')} {'needs' if blockers == 1 else 'need'} a change before it can go in the report. " if blockers else "")
             + "Could you help with these?", ""]
    for i, f in enumerate(sorted(findings, key=lambda f: SEVERITY_ORDER[f.severity]), 1):
        lines += [f"{i}. {f.ask}", f"   What I found: {f.message}", ""]
    lines += [f"Could you reply by {reply_by:%A, %b %d}? Once these are settled I'll update the figure and mark it approved.",
              "", "Thanks,", reviewer, ""]
    return "\n".join(lines)


def _pill(status):
    return f'<span class="pill {status}">{status.replace("_", " ")}</span>'


def write_html(path, report, rows, today):
    counts = {s: sum(r["status"] == s for r in rows) for s in ("approved", "waiting_on_answer", "needs_changes")}
    body = []
    for r in rows:
        items = "".join(f'<li class="{f["severity"]}"><b>{f["severity"]}</b> {html.escape(f["message"])}</li>'
                        for f in sorted(r["findings"], key=lambda f: SEVERITY_ORDER[f["severity"]])) or '<li class="ok">All checks passed.</li>'
        follow = f'<span class="flag">{html.escape(r["follow_up"])}</span>' if r["follow_up"] else ""
        body.append(f"""<tr><td class="num">{r['number']}</td><td><b>{html.escape(r['title'])}</b><br><code>{r['id']}</code></td>
<td>{html.escape(r['owner'])}</td><td>{_pill(r['status'])}</td><td class="num">{r['due']}</td>
<td class="num">{r['days_since_contact']}d {follow}</td><td class="num">{len(r['findings'])}</td></tr>
<tr class="detail"><td></td><td colspan="6"><ul>{items}</ul></td></tr>""")
    path.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Figure tracker</title>
<style>
:root{{--bg:#fff;--fg:#1f2330;--muted:#5b6170;--line:#e3e5ea;--ok:#1b7f6b;--warn:#a86a00;--bad:#c0392b}}
body{{font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--fg);background:var(--bg);margin:0;padding:32px max(16px,4vw)}}
h1{{font-size:1.6rem;margin:0 0 4px}} p.sub{{color:var(--muted);margin:0 0 24px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.card{{border:1px solid var(--line);padding:12px 16px;min-width:140px}} .card b{{display:block;font-size:1.8rem}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;min-width:760px}}
th,td{{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
td.num{{font-variant-numeric:tabular-nums;white-space:nowrap}} code{{color:var(--muted);font-size:.8rem}}
tr.detail td{{border-bottom:2px solid var(--line);padding-top:0}} ul{{margin:0;padding-left:18px}}
li{{margin:2px 0}} li b{{text-transform:uppercase;font-size:.7rem;letter-spacing:.06em;margin-right:6px}}
li.blocker b{{color:var(--bad)}} li.question b{{color:var(--warn)}} li.note b{{color:var(--muted)}} li.ok{{color:var(--ok)}}
.pill{{font-size:.75rem;padding:2px 8px;border-radius:99px;color:#fff;white-space:nowrap}}
.pill.approved{{background:var(--ok)}} .pill.waiting_on_answer{{background:var(--warn)}} .pill.needs_changes{{background:var(--bad)}}
.flag{{display:block;color:var(--bad);font-size:.75rem}}
</style></head><body>
<h1>{html.escape(report)}: figure tracker</h1><p class="sub">Checked against source data on {today:%B %d, %Y}.</p>
<div class="cards"><div class="card"><b>{len(rows)}</b>figures</div><div class="card"><b>{counts['approved']}</b>approved</div>
<div class="card"><b>{counts['waiting_on_answer']}</b>waiting on answer</div><div class="card"><b>{counts['needs_changes']}</b>need changes</div>
<div class="card"><b>{sum(1 for r in rows if r['follow_up'])}</b>need follow-up</div></div>
<div class="wrap"><table><thead><tr><th>#</th><th>Figure</th><th>Owner</th><th>Status</th><th>Due</th><th>Last contact</th><th>Issues</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div></body></html>""", encoding="utf-8")


def run(manifest_path, today=None, out_dir="out"):
    manifest_path = Path(manifest_path)
    root = manifest_path.parent
    m = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    today = today or date.today()
    out = root / out_dir
    (out / "feedback").mkdir(parents=True, exist_ok=True)
    rows = []
    for n, e in enumerate(m["figures"], 1):
        fig = json.loads((root / e["submitted"]).read_text(encoding="utf-8"))
        src = pd.read_csv(root / e["source"])
        findings = review_figure(e, fig, src)
        status = suggested_status(findings)
        (out / "feedback" / f"{n:02d}_{e['id']}.md").write_text(
            draft_feedback(e, fig, n, findings, m.get("reviewer", "Reviewer"), today), encoding="utf-8")
        rows.append({"number": n, "id": e["id"], "title": fig.get("title") or e["id"], "owner": e["owner"],
                     "status": status, "previous_status": e.get("status"), "due": str(e["due"]),
                     "days_since_contact": (today - e["last_contact"]).days,
                     "follow_up": needs_follow_up(e, status, today, m.get("follow_up_after_days", 3)),
                     "findings": [f.__dict__ for f in findings]})

    with open(out / "tracker.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "id", "owner", "status", "due", "days_since_contact", "follow_up", "blockers", "questions", "notes"])
        for r in rows:
            sev = [x["severity"] for x in r["findings"]]
            w.writerow([r["number"], r["id"], r["owner"], r["status"], r["due"], r["days_since_contact"],
                        r["follow_up"] or "", sev.count("blocker"), sev.count("question"), sev.count("note")])
    write_html(out / "tracker.html", m.get("report", "Report"), rows, today)
    fu = [r for r in rows if r["follow_up"]]
    lines = [f"# Follow-ups for {today:%B %d, %Y}", ""]
    lines += [f"- Figure {r['number']} ({r['id']}), {r['owner']}: {r['follow_up']}. "
              f"Status: {r['status'].replace('_', ' ')}, {_n(len(r['findings']), 'open item')}. "
              f"Draft: feedback/{r['number']:02d}_{r['id']}.md" for r in fu] or ["Nothing to chase today."]
    (out / "followups.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description="Check figures against source data and update the tracker.")
    p.add_argument("manifest", nargs="?", default="manifest.yaml")
    p.add_argument("--today", type=date.fromisoformat, help="review date (default: today)")
    p.add_argument("--out", default="out")
    a = p.parse_args(argv)
    rows = run(a.manifest, a.today, a.out)
    for r in rows:
        print(f"Figure {r['number']} {r['id']:<22} {r['status']:<18} {_n(len(r['findings']), 'issue')}"
              + (f"  -> follow up: {r['follow_up']}" if r["follow_up"] else ""))
    print(f"Wrote {a.out}/tracker.html, tracker.csv, followups.md and feedback/ drafts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
