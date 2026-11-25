"""
Machine-learning flood-risk component (Objective 3).

Trains a Random Forest to estimate area-level flood susceptibility from terrain
features (elevation, slope, distance to river, wetness proxy, elevation anomaly).
In a real deployment the labels would come from historical flood extents; here
the labels come from the flood simulator itself, so the module trains and
validates offline with no external data.

Limitation (see experiments/ml_validation.py): the labels are produced by the same
terrain-driven simulator, and an elevation-only rule scores about the same AUC as
the forest on the training terrain. The forest's gain is small and appears mainly
on unseen terrains. Treat the score as a check that the pipeline works, not as a
predictor of real floods.

What the risk surface does in the platform: it only weights where residents live
(population placement). It does not change the flood itself or the optimiser, and
the reported Chapter 4 experiments do not use it.
"""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

from .config import SimConfig
from .grid import Terrain
from .flood import FloodModel


def _features(terrain: Terrain):
    """Per-cell feature stack: elevation, slope, distance-to-river, wetness, aspect."""
    elev = terrain.elevation
    gy, gx = np.gradient(elev)
    slope = np.sqrt(gx ** 2 + gy ** 2)
    n = terrain.size
    yy, xx = np.mgrid[0:n, 0:n]
    river_col = (n / 2) + (n / 6) * np.sin(2 * np.pi * yy / n * 1.3)
    dist_river = np.abs(xx - river_col)
    # topographic wetness proxy: low, flat areas are wetter
    wetness = 1.0 / (1.0 + slope) * np.exp(-(elev - elev.min()) / 8.0)
    feats = np.stack([
        elev.ravel(),
        slope.ravel(),
        dist_river.ravel(),
        wetness.ravel(),
        (elev - elev.mean()).ravel(),
    ], axis=1)
    return feats


class FloodRiskModel:
    def __init__(self):
        self.clf = RandomForestClassifier(n_estimators=120, max_depth=12, random_state=0, n_jobs=-1)
        self.metrics = {}
        self.trained = False

    def train(self, cfg: SimConfig | None = None, seed: int = 0):
        cfg = cfg or SimConfig()
        terrain = Terrain(cfg.grid_size, cfg.cell_km, seed)
        X = _features(terrain)
        # label = did this cell flood beyond the evacuate depth in a reference run?
        fm = FloodModel(terrain, cfg)
        for _ in range(cfg.total_steps):
            fm.step()
        y = (fm.water >= cfg.evacuate_depth).ravel().astype(int)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=seed, stratify=y)
        self.clf.fit(Xtr, ytr)
        proba = self.clf.predict_proba(Xte)[:, 1]
        self.metrics = {
            "accuracy": round(float(accuracy_score(yte, (proba > 0.5).astype(int))), 3),
            "roc_auc": round(float(roc_auc_score(yte, proba)), 3),
            # baseline: rank cells by lowest elevation (same held-out split)
            "elevation_baseline_auc": round(float(roc_auc_score(yte, -Xte[:, 0])), 3),
            "n_samples": int(len(y)),
            "flood_positives": int(y.sum()),
        }
        self.trained = True
        return self.metrics

    def risk_surface(self, terrain: Terrain):
        """Return a grid of flood-susceptibility probabilities (0..1)."""
        if not self.trained:
            self.train()
        X = _features(terrain)
        p = self.clf.predict_proba(X)[:, 1]
        return p.reshape(terrain.size, terrain.size)

    def feature_importance(self):
        names = ["elevation", "slope", "dist_to_river", "wetness", "elev_anomaly"]
        if not self.trained:
            return {}
        return {n: round(float(v), 3) for n, v in zip(names, self.clf.feature_importances_)}
