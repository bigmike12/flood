"""
Flood propagation via a cellular automaton (CA).

Each cell holds a water depth. On each step:
  1. a rainfall/river source term adds water;
  2. water is redistributed from every cell to its lower-head neighbours in
     proportion to the head difference.

This approximates the diffusion-wave form of the shallow-water equations and is
the fast, interactive alternative to a full hydrodynamic solver (see Wang et al.,
2021; Agonafir et al., 2023). The scheme conserves mass except for the explicit
source term (verified by tests/test_core.py).
"""
from __future__ import annotations
import numpy as np
from .config import SimConfig
from .grid import Terrain

# 8-neighbour offsets
_NEIGHBOURS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


class FloodModel:
    def __init__(self, terrain: Terrain, cfg: SimConfig):
        self.terrain = terrain
        self.cfg = cfg
        self.n = terrain.size
        self.water = np.zeros((self.n, self.n), dtype=np.float64)
        self.step_i = 0
        self.total_rain_added = 0.0

    def _source(self):
        """Add rainfall everywhere and a stronger inflow along the river."""
        c = self.cfg
        if self.step_i >= c.rain_steps:
            return
        # rainfall in metres this step, scaled by intensity
        rain_m = (c.rainfall_mm / 1000.0) * c.flood_intensity
        self.water += rain_m
        self.total_rain_added += rain_m * self.n * self.n
        # river inflow: extra water in the channel (upstream flooding)
        river = self.terrain.river_mask
        extra = rain_m * 3.5
        self.water[river] += extra
        self.total_rain_added += extra * int(river.sum())

    def step(self):
        c = self.cfg
        self._source()
        elev = self.terrain.elevation
        head = elev + self.water            # water surface elevation

        # Pass 1: head drop to each neighbour (0 across grid edges).
        drops = []
        total_drop = np.zeros_like(self.water)
        for dr, dc in _NEIGHBOURS:
            shifted_head = np.roll(np.roll(head, -dr, axis=0), -dc, axis=1)
            drop = _mask_edges(head - shifted_head, dr, dc)
            drop = np.clip(drop, 0.0, None)
            drops.append(drop)
            total_drop += drop

        # Per-cell outflow, limited by available water and the flow coefficient.
        with np.errstate(invalid="ignore", divide="ignore"):
            outflow = np.minimum(self.water, c.flow_coeff * total_drop)
        safe_total = np.where(total_drop > 0, total_drop, 1.0)

        # Pass 2: distribute outflow to lower neighbours in proportion to drop.
        new_water = self.water - outflow
        for (dr, dc), drop in zip(_NEIGHBOURS, drops):
            flow = outflow * (drop / safe_total)          # amount leaving toward this neighbour
            new_water += np.roll(np.roll(flow, dr, axis=0), dc, axis=1)
        self.water = np.clip(new_water, 0.0, None)
        self.step_i += 1
        return self.water

    def depth_grid(self):
        """Water depth clipped to the reportable threshold."""
        d = self.water.copy()
        d[d < self.cfg.min_flood_depth] = 0.0
        return d

    def flooded_fraction(self):
        return float((self.water >= self.cfg.evacuate_depth).mean())


def _mask_edges(arr, dr, dc):
    """Zero the drop for cells whose (dr, dc) neighbour lies outside the grid,
    so no water flows across the boundary (mass stays on the grid)."""
    out = arr.copy()
    if dr == 1:
        out[-1, :] = 0.0     # last row has no cell below
    elif dr == -1:
        out[0, :] = 0.0      # first row has no cell above
    if dc == 1:
        out[:, -1] = 0.0     # last col has no cell to the right
    elif dc == -1:
        out[:, 0] = 0.0      # first col has no cell to the left
    return out
