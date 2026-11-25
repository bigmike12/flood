"""
Scenario construction and generation (supports Objectives 3 and 4).

Builds a SimConfig + Terrain (+ optional ML risk surface) from a high-level
scenario description, and constructs a ready-to-run FloodResponseModel.
"""
from __future__ import annotations
from dataclasses import replace

from .config import SimConfig, REGIONS, DEFAULT_REGION
from .grid import Terrain
from .model import FloodResponseModel
from .ml_risk import FloodRiskModel

# a single shared, lazily-trained risk model
_RISK = FloodRiskModel()


def build_model(region: str = DEFAULT_REGION, flood_intensity: float = 0.6,
                rainfall_mm: float = 60.0, strategy: str = "ai_optimised",
                seed: int = 42, use_risk: bool = True, **overrides) -> FloodResponseModel:
    reg = REGIONS.get(region, REGIONS[DEFAULT_REGION])
    cfg = SimConfig(seed=seed, flood_intensity=flood_intensity,
                    rainfall_mm=rainfall_mm, strategy=strategy, **overrides)
    terrain = Terrain(cfg.grid_size, cfg.cell_km, seed,
                      center_lat=reg["lat"], center_lng=reg["lng"], region_key=region)
    risk = _RISK.risk_surface(terrain) if use_risk else None
    return FloodResponseModel(cfg, terrain=terrain, risk_surface=risk)


def risk_metrics():
    if not _RISK.trained:
        _RISK.train()
    return {"metrics": _RISK.metrics, "feature_importance": _RISK.feature_importance()}


def region_list():
    return [{"id": k, **v} for k, v in REGIONS.items()]
