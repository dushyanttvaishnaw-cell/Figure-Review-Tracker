"""Checks that compare a submitted figure with its source data."""
import re
from dataclasses import dataclass, field

import pandas as pd

NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%")
UNIT = re.compile(r"\(([^)]+)\)")


@dataclass
class Finding:
    check: str
    severity: str  # "blocker" must be fixed, "question" needs an answer, "note" is minor
    message: str
    ask: str       # what the reviewer needs from the figure owner
    details: dict = field(default_factory=dict)


def _key(row, keys):
    return tuple(float(row[k]) if isinstance(row[k], (int, float)) else str(row[k]) for k in keys)


def compare_values(plotted, source, keys, values, decimals):
    """Every plotted value must equal the source value at the stated precision; no rows may be missing or extra."""
    out, tol = [], 0.5 * 10 ** (-decimals) + 1e-9
    src = {_key(r, keys): r for r in source.to_dict("records")}
    seen = set()
    for row in plotted:
        k = _key(row, keys)
        label = ", ".join(str(row[x]) for x in keys)
        if k not in src:
            out.append(Finding("extra_row", "blocker", f"The chart shows a point for {label} that is not in the source file.",
                               f"Can you confirm where the {label} value comes from, or remove it?", {"row": label}))
            continue
        seen.add(k)
        for v in values:
            a, b = float(row[v]), float(src[k][v])
            if abs(a - b) > tol:
                out.append(Finding("value_mismatch", "blocker",
                                   f"{label}: the chart shows {v} = {a:g}, but the source file has {b:g}.",
                                   f"Which value is correct for {label}: {a:g} (chart) or {b:g} (source)?",
                                   {"row": label, "column": v, "chart": a, "source": b}))
    for k, r in src.items():
        if k not in seen:
            label = ", ".join(str(r[x]) for x in keys)
            out.append(Finding("missing_row", "blocker", f"The source file has {label}, but it is not in the chart.",
                               f"Should {label} be in the chart? If it was left out on purpose, can we say why in the caption?",
                               {"row": label}))
    return out


def check_caption_numbers(caption, source, values, decimals, allow=()):
    """Every percentage quoted in the caption must appear in the source data (at the stated precision)."""
    pool = set()
    for v in values:
        pool |= {round(float(x), decimals) for x in source[v].dropna()}
    out = []
    for m in NUMBER.finditer(caption or ""):
        n = round(float(m.group(1)), decimals)
        if n in pool or float(m.group(1)) in allow:
            continue
        out.append(Finding("caption_number", "question", f"The caption quotes {m.group(0)}, which does not match any value in the source data.",
                           f"Where does {m.group(0)} in the caption come from? If it is a threshold or a derived number, can we say so?",
                           {"number": m.group(0)}))
    return out


def check_claims(claims, source):
    """Verify written claims (e.g. 'Model E is highest on every suite') against the data."""
    out = []
    for c in claims or []:
        df, t = source, c["type"]
        for col, val in (c.get("filter") or {}).items():
            df = df[df[col] == val]
        if t == "max" or t == "min":
            pick = df.loc[df.groupby(c["group_by"])[c["column"]].idxmax() if t == "max"
                          else df.groupby(c["group_by"])[c["column"]].idxmin()]
            wrong = pick[pick[c["entity_col"]] != c["entity"]]
            ok = wrong.empty
            detail = "; ".join(f"{r[c['group_by']]}: {r[c['entity_col']]} ({r[c['column']]:g})" for _, r in wrong.iterrows())
        elif t == "all_above":
            wrong = df[df[c["column"]] <= c["threshold"]]
            ok = wrong.empty
            detail = f"{len(wrong)} of {len(df)} values are at or below {c['threshold']}, lowest is {df[c['column']].min():g}"
        elif t == "all_less":
            wrong = df[df[c["column"]] >= df[c["than"]]]
            ok = wrong.empty
            detail = f"{len(wrong)} row(s) where {c['column']} is not below {c['than']}"
        else:
            raise ValueError(f"Unknown claim type: {t}")
        if not ok:
            out.append(Finding("claim", "blocker", f"The claim \"{c['text']}\" does not hold in the data ({detail}).",
                               f"Can we reword \"{c['text']}\" so it matches the data, or is there newer data I should use?",
                               {"claim": c["text"], "detail": detail}))
    return out


def check_labels(fig):
    out = []
    if not fig.get("title"):
        out.append(Finding("title", "blocker", "The figure has no title.", "What is the one-line takeaway for the title?"))
    for key in ("x_label", "y_label"):
        text = fig.get(key) or ""
        if not text:
            out.append(Finding("label", "blocker", f"The {key.replace('_', ' ')} is missing.", f"What should the {key.replace('_', ' ')} say?"))
        elif not UNIT.search(text):
            out.append(Finding("units", "question", f"The {key.replace('_', ' ')} \"{text}\" has no unit.",
                               f"What unit is \"{text}\" in (for example %, points, or count)?"))
    if not re.match(r"^Figure \d+\.", fig.get("caption") or ""):
        out.append(Finding("caption_format", "note", "The caption does not start with \"Figure N.\"", "OK to add the figure number?"))
    return out


def review_figure(entry, fig, source):
    findings = check_labels(fig)
    findings += compare_values(fig["plotted"], source, entry["keys"], entry["values"], entry.get("decimals", 1))
    findings += check_caption_numbers(fig.get("caption"), source, entry["values"], entry.get("decimals", 1),
                                      entry.get("caption_allow", ()))
    findings += check_claims(entry.get("claims"), source)
    return findings
