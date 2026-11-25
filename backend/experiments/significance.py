"""
Paired significance tests for the strategy comparison (Chapter 4).

Each seed is run under every strategy, so comparisons are paired by seed. For each
difference we report the mean, a 95% bootstrap confidence interval, a paired t-test
and a Wilcoxon signed-rank test. Reads experiments/results/runs.csv (written by
run_experiments.py) and writes experiments/results/significance.json.

Run from backend/:   python -m experiments.significance
"""
from __future__ import annotations

import csv
import json
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "results", "runs.csv")
OUT = os.path.join(HERE, "results", "significance.json")


def column(rows, strategy: str, key: str) -> np.ndarray:
    by_seed = {int(r["seed"]): float(r[key]) for r in rows if r["strategy"] == strategy}
    return np.array([by_seed[s] for s in sorted(by_seed)])


def compare(a: np.ndarray, b: np.ndarray, seed: int = 0) -> dict:
    diff = a - b
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(diff, len(diff)).mean() for _ in range(5000)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "mean_diff": round(float(diff.mean()), 3),
        "ci95": [round(float(lo), 3), round(float(hi), 3)],
        "paired_t_p": float(stats.ttest_rel(a, b).pvalue),
        "wilcoxon_p": float(stats.wilcoxon(a, b).pvalue),
        "n_seeds": int(len(diff)),
    }


def main() -> dict:
    with open(RUNS) as f:
        rows = list(csv.DictReader(f))
    out = {}
    for key in ("coverage_pct", "casualties"):
        ai = column(rows, "ai_optimised", key)
        for other in ("random", "nearest", "pop_proportional"):
            out[f"ai_minus_{other}_{key}"] = compare(ai, column(rows, other, key))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    for name, r in main().items():
        print(f"{name:34s} diff {r['mean_diff']:+7.2f}  95% CI [{r['ci95'][0]:+.2f}, {r['ci95'][1]:+.2f}]  "
              f"t p={r['paired_t_p']:.2g}  Wilcoxon p={r['wilcoxon_p']:.2g}")
