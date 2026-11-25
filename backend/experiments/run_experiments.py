"""
Evaluation harness (Objective 5).

Runs each allocation strategy over many random seeds on the same scenario,
collects KPIs, writes a results table (CSV + JSON) and the comparison charts used
as the Chapter 4 figures. Run:

    python -m experiments.run_experiments --seeds 30
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SimConfig
from app.model import FloodResponseModel

STRATEGIES = ["random", "nearest", "pop_proportional", "ai_optimised"]
LABELS = {
    "random": "Random",
    "nearest": "Nearest-depot",
    "pop_proportional": "Population-proportional",
    "ai_optimised": "AI-optimised",
}
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def run(seeds=30, grid=36):
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    per_strategy = {s: [] for s in STRATEGIES}
    for strat in STRATEGIES:
        for seed in range(seeds):
            cfg = SimConfig(grid_size=grid, seed=seed, strategy=strat)
            m = FloodResponseModel(cfg)
            k = m.run().to_dict()
            k["strategy"] = strat
            k["seed"] = seed
            rows.append(k)
            per_strategy[strat].append(k)

    summary = {}
    for strat in STRATEGIES:
        ks = per_strategy[strat]
        summary[strat] = {
            "mean_response_time": round(st.mean(x["mean_response_time"] for x in ks), 2),
            "response_time_sd": round(st.pstdev(x["mean_response_time"] for x in ks), 2),
            "coverage_pct": round(st.mean(x["coverage_pct"] for x in ks), 1),
            "casualties": round(st.mean(x["casualties"] for x in ks), 1),
            "utilisation_pct": round(st.mean(x["utilisation_pct"] for x in ks), 1),
        }

    # casualties averted vs the random baseline (lives saved relative to no coordination)
    base_cas = summary["random"]["casualties"]
    for strat in STRATEGIES:
        summary[strat]["casualties_averted_vs_random"] = round(base_cas - summary[strat]["casualties"], 1)

    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(OUT_DIR, "runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    _print_table(summary)
    try:
        _plot(summary, per_strategy)
    except Exception as e:   # matplotlib optional
        print("(charts skipped:", e, ")")
    return summary


def _print_table(summary):
    print("\n=== Strategy comparison (mean over seeds) ===")
    print(f"{'Strategy':24s}{'Resp.time':>11s}{'Coverage%':>11s}{'Casualties':>12s}{'Util%':>8s}{'Averted':>9s}")
    for strat in STRATEGIES:
        s = summary[strat]
        print(f"{LABELS[strat]:24s}{s['mean_response_time']:>11}{s['coverage_pct']:>11}"
              f"{s['casualties']:>12}{s['utilisation_pct']:>8}{s['casualties_averted_vs_random']:>9}")


def _plot(summary, per_strategy):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    NAVY, BLUE, ACCENT, GREY = "#0B2A4A", "#2E4A7A", "#E0872A", "#888888"
    labels = [LABELS[s] for s in STRATEGIES]
    colors = [GREY, BLUE, BLUE, ACCENT]

    # 1) response time
    rt = [summary[s]["mean_response_time"] for s in STRATEGIES]
    sd = [summary[s]["response_time_sd"] for s in STRATEGIES]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(labels, rt, yerr=sd, capsize=5, color=colors, edgecolor=NAVY)
    ax.set_ylabel("Mean response time (min)"); ax.set_title("Mean Response Time by Strategy")
    plt.xticks(rotation=15); fig.tight_layout(); fig.savefig(os.path.join(OUT_DIR, "fig_response_time.png"), dpi=150); plt.close(fig)

    # 2) coverage & casualties averted
    cov = [summary[s]["coverage_pct"] for s in STRATEGIES]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(labels, cov, color=colors, edgecolor=NAVY)
    ax.set_ylabel("Demand coverage (%)"); ax.set_title("Demand Coverage by Strategy"); ax.set_ylim(0, 100)
    plt.xticks(rotation=15); fig.tight_layout(); fig.savefig(os.path.join(OUT_DIR, "fig_coverage.png"), dpi=150); plt.close(fig)

    # 3) casualties
    cas = [summary[s]["casualties"] for s in STRATEGIES]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(labels, cas, color=colors, edgecolor=NAVY)
    ax.set_ylabel("Mean casualties"); ax.set_title("Casualties by Strategy")
    plt.xticks(rotation=15); fig.tight_layout(); fig.savefig(os.path.join(OUT_DIR, "fig_casualties.png"), dpi=150); plt.close(fig)
    print(f"\nCharts written to {OUT_DIR}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--grid", type=int, default=36)
    args = ap.parse_args()
    run(seeds=args.seeds, grid=args.grid)
