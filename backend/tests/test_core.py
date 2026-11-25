"""
Core tests (Objective 5 verification): flood mass conservation, road closure,
optimiser feasibility, deterministic reproducibility, and KPI sanity.

Run:  pytest -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SimConfig
from app.grid import Terrain
from app.flood import FloodModel
from app.model import FloodResponseModel


def test_flood_conserves_mass():
    cfg = SimConfig(grid_size=30, seed=1)
    t = Terrain(cfg.grid_size, cfg.cell_km, cfg.seed)
    f = FloodModel(t, cfg)
    for _ in range(cfg.total_steps):
        f.step()
    err = abs(f.water.sum() - f.total_rain_added) / f.total_rain_added
    assert err < 0.01, f"mass error too high: {err:.4f}"


def test_roads_close_when_flooded():
    cfg = SimConfig(grid_size=30, seed=2, flood_intensity=0.9)
    m = FloodResponseModel(cfg)
    m.run()
    assert m.roads.closed_fraction > 0.0, "expected some roads to close in a severe flood"


def test_reproducible():
    def run():
        cfg = SimConfig(grid_size=30, seed=5, strategy="ai_optimised")
        return FloodResponseModel(cfg).run().to_dict()
    a, b = run(), run()
    assert a == b, "same seed must give identical KPIs"


def test_optimiser_beats_random():
    """AI-optimised should clearly beat uncoordinated (random) dispatch on the
    robust headline metric: demand coverage (averaged over seeds)."""
    def avg_coverage(strat, seeds=8):
        vals = []
        for s in range(seeds):
            cfg = SimConfig(grid_size=36, seed=s, strategy=strat)
            vals.append(FloodResponseModel(cfg).run().coverage_pct)
        return sum(vals) / len(vals)
    ai = avg_coverage("ai_optimised")
    rnd = avg_coverage("random")
    assert ai > rnd + 3.0, f"AI coverage ({ai:.1f}) should exceed random ({rnd:.1f}) by a clear margin"


def test_kpis_bounded():
    cfg = SimConfig(grid_size=30, seed=7)
    k = FloodResponseModel(cfg).run().to_dict()
    assert 0 <= k["coverage_pct"] <= 100
    assert 0 <= k["utilisation_pct"] <= 100
    assert k["casualties"] >= 0 and k["rescued"] >= 0


def test_ortools_matches_hungarian():
    """The two optimal solvers (Hungarian via SciPy and Google OR-Tools CP-SAT)
    must reach the same optimal objective and the same number of assignments on
    every test instance. Skipped if OR-Tools is not installed."""
    import numpy as np
    import app.optimizer as o
    if o._optimal_ortools(np.array([[1.0]]), np.array([[1.0]])) is None:
        import pytest
        pytest.skip("OR-Tools not installed")
    rng = np.random.default_rng(0)
    for _ in range(50):
        nu, nd = int(rng.integers(3, 12)), int(rng.integers(3, 12))
        cost = rng.uniform(1, 50, size=(nu, nd))
        cost[rng.random((nu, nd)) < 0.2] = o.UNREACHABLE
        rows, cols = o.linear_sum_assignment(cost)
        hun = {int(i): int(j) for i, j in zip(rows, cols) if cost[i, j] < o.UNREACHABLE / 2}
        ort = o._optimal_ortools(cost.copy(), cost.copy())
        cost_h = sum(cost[i, j] for i, j in hun.items())
        cost_o = sum(cost[i, j] for i, j in ort.items())
        assert len(hun) == len(ort), "solvers disagree on number of assignments"
        assert abs(cost_h - cost_o) < 1e-2, "solvers disagree on optimal objective"
