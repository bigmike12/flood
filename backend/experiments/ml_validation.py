"""
Validation of the flood-susceptibility model (Objective 3), beyond the single
random split reported in the app.

Questions this answers:
  1. Does the current protocol (random 70/30 split of grid cells on one terrain)
     overstate performance? Grid cells are spatially correlated, so a random split
     leaks information between neighbouring train and test cells.
  2. Does the Random Forest beat trivial baselines (lowest-elevation ranking,
     logistic regression) on the same features?
  3. Does it generalise to an unseen terrain (different DEM seed)?
  4. How prevalent is the positive class, and how well calibrated are the scores?

Run from backend/:   python -m experiments.ml_validation
Writes experiments/results/ml_validation.json and prints a summary.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SimConfig
from app.grid import Terrain
from app.flood import FloodModel
from app.ml_risk import _features, FloodRiskModel

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "ml_validation.json")
N_TERRAINS = 6   # DEM seeds 0..5


def dataset(seed: int, cfg: SimConfig):
    """Features and labels for one terrain, exactly as the app builds them."""
    terrain = Terrain(cfg.grid_size, cfg.cell_km, seed)
    X = _features(terrain)
    fm = FloodModel(terrain, cfg)
    for _ in range(cfg.total_steps):
        fm.step()
    y = (fm.water >= cfg.evacuate_depth).ravel().astype(int)
    return X, y, terrain.size


def rf() -> RandomForestClassifier:
    # same hyper-parameters as app/ml_risk.py
    return RandomForestClassifier(n_estimators=120, max_depth=12, random_state=0, n_jobs=-1)


def block_ids(n: int, block: int = 10) -> np.ndarray:
    """Spatial block label for each cell of an n x n grid (block x block tiles)."""
    yy, xx = np.mgrid[0:n, 0:n]
    return ((yy // block) * (n // block) + (xx // block)).ravel()


def main() -> dict:
    cfg = SimConfig()
    data = [dataset(s, cfg) for s in range(N_TERRAINS)]
    results: dict = {"n_terrains": N_TERRAINS, "grid": cfg.grid_size}

    X0, y0, n = data[0]
    results["positive_rate"] = round(float(y0.mean()), 3)
    results["n_cells"] = int(len(y0))

    # 1) current protocol: random stratified 70/30 split on terrain 0
    Xtr, Xte, ytr, yte = train_test_split(X0, y0, test_size=0.3, random_state=0, stratify=y0)
    m = rf().fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    results["rf_random_split_auc"] = round(float(roc_auc_score(yte, p)), 3)
    results["rf_random_split_brier"] = round(float(brier_score_loss(yte, p)), 3)

    # 2) spatial block cross-validation on terrain 0 (hold out whole 10x10 tiles)
    groups = block_ids(n)
    folds = np.unique(groups)
    rng = np.random.default_rng(0)
    rng.shuffle(folds)
    chunks = np.array_split(folds, 4)
    rf_aucs, base_aucs, lr_aucs = [], [], []
    for chunk in chunks:
        te = np.isin(groups, chunk)
        tr = ~te
        if len(np.unique(y0[te])) < 2 or len(np.unique(y0[tr])) < 2:
            continue
        mrf = rf().fit(X0[tr], y0[tr])
        rf_aucs.append(roc_auc_score(y0[te], mrf.predict_proba(X0[te])[:, 1]))
        base_aucs.append(roc_auc_score(y0[te], -X0[te, 0]))          # lowest elevation = most susceptible
        lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X0[tr], y0[tr])
        lr_aucs.append(roc_auc_score(y0[te], lr.predict_proba(X0[te])[:, 1]))
    results["spatial_cv_rf_auc"] = round(float(np.mean(rf_aucs)), 3)
    results["spatial_cv_rf_auc_folds"] = [round(float(a), 3) for a in rf_aucs]
    results["spatial_cv_lowest_elevation_auc"] = round(float(np.mean(base_aucs)), 3)
    results["spatial_cv_logistic_auc"] = round(float(np.mean(lr_aucs)), 3)

    # 3) baselines on the random split (same split as step 1)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(Xtr, ytr)
    results["logistic_random_split_auc"] = round(float(roc_auc_score(yte, lr.predict_proba(Xte)[:, 1])), 3)
    results["lowest_elevation_random_split_auc"] = round(float(roc_auc_score(yte, -Xte[:, 0])), 3)

    # 4) cross-terrain: train on terrain 0, test on each unseen terrain
    cross = {}
    m0 = rf().fit(X0, y0)
    for s in range(1, N_TERRAINS):
        Xs, ys, _ = data[s]
        cross[f"terrain_{s}"] = round(float(roc_auc_score(ys, m0.predict_proba(Xs)[:, 1])), 3)
    results["cross_terrain_rf_auc"] = cross
    results["cross_terrain_lowest_elevation_auc"] = {
        f"terrain_{s}": round(float(roc_auc_score(data[s][1], -data[s][0][:, 0])), 3) for s in range(1, N_TERRAINS)}

    # 5) what the forest actually uses: drop the features built from the river formula
    names = ["elevation", "slope", "dist_to_river", "wetness", "elev_anomaly"]
    keep = [0, 1, 3, 4]   # without dist_to_river
    m_nodist = rf().fit(Xtr[:, keep], ytr)
    results["rf_without_dist_river_auc"] = round(float(roc_auc_score(yte, m_nodist.predict_proba(Xte[:, keep])[:, 1])), 3)
    results["feature_importance_terrain0"] = {k: round(float(v), 3) for k, v in zip(names, m.feature_importances_)}

    # 6) what the app reports today (for the same protocol)
    app_metrics = FloodRiskModel().train(cfg=cfg, seed=0)
    results["app_reported_metrics"] = app_metrics

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    return results


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=2))
