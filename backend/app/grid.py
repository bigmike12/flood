"""
Terrain grid and synthetic Digital Elevation Model (DEM).

A real deployment would load a GeoTIFF DEM. To keep the MVP runnable offline with
zero external data, we generate a plausible DEM with a river valley cutting through
sloped terrain. The generator is deterministic given the seed.
"""
from __future__ import annotations
import numpy as np


class Terrain:
    def __init__(self, size: int, cell_km: float, seed: int = 42,
                 center_lat: float = 7.802, center_lng: float = 6.744,
                 region_key: str = ""):
        self.size = size
        self.cell_km = cell_km
        self.center_lat = center_lat
        self.center_lng = center_lng
        # The terrain must differ by region, not just the map centre. We derive a
        # stable per-region offset from the region name and fold it into both the
        # random seed and the river-geometry parameters, so each region produces a
        # distinct DEM (and therefore a distinct flood and different results).
        self.region_key = region_key
        rcode = sum(ord(ch) for ch in region_key) if region_key else 0
        self.rng = np.random.default_rng(seed + 1009 * rcode)
        if rcode == 0:
            # default / benchmark terrain (unchanged, so evaluation stays stable)
            self._river_amp, self._river_freq, self._river_phase, self._slope_sign = 1.0 / 6.0, 1.3, 0.0, 1.0
        else:
            # region-specific river geometry
            self._river_amp = 1.0 / 6.0 + 0.06 * ((rcode % 5) - 2) / 5.0     # meander width
            self._river_freq = 1.3 + 0.5 * ((rcode % 7) - 3) / 7.0           # meander frequency
            self._river_phase = (rcode % 11) / 11.0 * 2 * np.pi             # meander phase
            self._slope_sign = 1.0 if (rcode % 2 == 0) else -1.0            # slope direction
        self.elevation = self._make_dem()
        self.river_mask = self._river_channel()

    def _river_col(self, yy):
        n = self.size
        return (n / 2) + (n * self._river_amp) * np.sin(
            2 * np.pi * yy / n * self._river_freq + self._river_phase)

    def _make_dem(self) -> np.ndarray:
        n = self.size
        yy, xx = np.mgrid[0:n, 0:n]
        # gentle regional slope (direction varies by region)
        base = 40.0 + 0.6 * ((n - yy) + self._slope_sign * (n - xx))
        # a meandering river valley following the region-specific path
        dist_to_river = np.abs(xx - self._river_col(yy))
        valley = -9.0 * np.exp(-(dist_to_river ** 2) / (2 * (n * 0.09) ** 2))
        # correlated noise for realism
        noise = self.rng.normal(0, 1.0, (n, n))
        for _ in range(3):  # smooth the noise
            noise = 0.25 * (
                np.roll(noise, 1, 0) + np.roll(noise, -1, 0)
                + np.roll(noise, 1, 1) + np.roll(noise, -1, 1)
            )
        dem = base + valley + 2.5 * noise
        return dem.astype(np.float64)

    def _river_channel(self) -> np.ndarray:
        n = self.size
        yy, xx = np.mgrid[0:n, 0:n]
        return (np.abs(xx - self._river_col(yy)) < 1.2)

    def cell_to_latlng(self, row: int, col: int):
        """Map a grid cell to approximate lat/lng for the map view."""
        n = self.size
        deg_per_cell = (self.cell_km / 111.0)  # ~111 km per degree
        lat = self.center_lat + (n / 2 - row) * deg_per_cell
        lng = self.center_lng + (col - n / 2) * deg_per_cell
        return lat, lng

    def bounds(self):
        tl = self.cell_to_latlng(0, 0)
        br = self.cell_to_latlng(self.size - 1, self.size - 1)
        return {"south": br[0], "west": tl[1], "north": tl[0], "east": br[1]}
