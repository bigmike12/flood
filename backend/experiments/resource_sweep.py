"""
Resource-level sweep: does the AI advantage grow when responders are scarce?

Runs the report setup (same as run_experiments.py) at several responder-unit
counts, 30 seeds each, for random and AI-optimised, and records coverage and
casualties with paired differences. Writes experiments/results/resource_sweep.json.

Run from backend/:   python -m experiments.resource_sweep
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SimConfig
from app.model import FloodResponseModel

UNITS = (4, 10, 20)
SEEDS = 30
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "resource_sweep.json")


def run(strategy: str, units: int, seed: int) -> dict:
    cfg = SimConfig(grid_size=36, seed=seed, strategy=strategy, n_responder_units=units)
    return FloodResponseModel(cfg).run().to_dict()


def main() -> dict:
    out = {}
    for units in UNITS:
        rnd = [run("random", units, s) for s in range(SEEDS)]
        ai = [run("ai_optimised", units, s) for s in range(SEEDS)]
        cov_r = st.mean(k["coverage_pct"] for k in rnd)
        cov_a = st.mean(k["coverage_pct"] for k in ai)
        cas_r = st.mean(k["casualties"] for k in rnd)
        cas_a = st.mean(k["casualties"] for k in ai)
        out[str(units)] = {
            "random": {"coverage_pct": round(cov_r, 1), "casualties": round(cas_r, 1)},
            "ai_optimised": {"coverage_pct": round(cov_a, 1), "casualties": round(cas_a, 1)},
            "coverage_gain": round(cov_a - cov_r, 1),
            "casualties_averted": round(cas_r - cas_a, 1),
            "seeds": SEEDS,
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    for units, r in main().items():
        print(f"units={units:>2}: coverage gain {r['coverage_gain']:+.1f} pts, casualties averted {r['casualties_averted']:.1f}")
