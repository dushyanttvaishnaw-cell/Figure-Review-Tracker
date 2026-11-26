"""Create the sample 'submitted figure' files used in the demo.

They start from figures exported by eval-figure-kit (exact plotted values +
caption) and then have realistic mistakes planted in them, so the review tool
has something to catch. Each planted mistake is listed in PLANTED below.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "submissions"

PLANTED = {
    "benchmark_accuracy": "Model C / Coding score typed as 59.1; the source says 59.9.",
    "compute_scaling": "Family Y at 1e22 FLOP left out of the chart; y-axis label has no unit.",
    "refusal_heatmap": "Caption claims Model E refused over 95% in every category (not true in the data).",
    "jailbreak_mitigation": "No planted mistakes. This one should pass.",
}


def rows(csv):
    return pd.read_csv(DATA / csv).to_dict("records")


def main():
    OUT.mkdir(exist_ok=True)
    bench = rows("benchmark_scores.csv")
    for r in bench:
        r.pop("n_items")
        if r["model"] == "Model C" and r["benchmark"] == "Coding":
            r["score_pct"] = 59.1  # source says 59.9
    figs = {
        "benchmark_accuracy": {
            "title": "Model E leads on all four benchmarks", "x_label": "Benchmark (task suite)", "y_label": "Accuracy (%)",
            "caption": "Figure 1. Accuracy of five models on four benchmark suites. Error bars show 95% confidence "
                       "intervals. Model E scores highest on every suite, reaching 87.9% on Reading.",
            "plotted": bench},
        "compute_scaling": {
            "title": "Scores rise steadily with training compute", "x_label": "Training compute (FLOP, log scale)",
            "y_label": "Benchmark score",
            "caption": "Figure 2. Average benchmark score against training compute for two model families. "
                       "Family X reaches 55.5% at the largest budget.",
            "plotted": [r for r in rows("scaling.csv")
                        if not (r["family"] == "Family Y" and r["training_compute_flop"] == 1e22)]},
        "refusal_heatmap": {
            "title": "Refusal rates on harmful requests, by category", "x_label": "Model (name)", "y_label": "Refusal rate (%)",
            "caption": "Figure 3. Share of harmful test requests each model refused, by category. "
                       "Model E refused over 95% of requests in every category.",
            "plotted": rows("refusal_rates.csv")},
        "jailbreak_mitigation": {
            "title": "The mitigation cut jailbreak success for every model", "x_label": "Jailbreak success rate (%)",
            "y_label": "Model (name)",
            "caption": "Figure 4. Share of jailbreak attempts that succeeded before and after the mitigation. "
                       "Model A fell from 41.0% to 15.5%.",
            "plotted": rows("jailbreak_mitigation.csv")},
    }
    for fid, rec in figs.items():
        (OUT / f"{fid}.json").write_text(json.dumps({"id": fid, **rec}, indent=2), encoding="utf-8")
    print("Wrote", len(figs), "submissions. Planted mistakes:")
    for k, v in PLANTED.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
