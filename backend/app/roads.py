"""
Road network and flood-dependent accessibility.

A real deployment would load an OpenStreetMap road graph. For the MVP we build a
grid road network over the terrain (nodes = cells). Each edge's travel cost rises
with water depth and the edge is closed once depth exceeds a threshold, following
the depth-disruption idea (Alabbad et al., 2021; Yin et al., 2020). Travel time
between points is the shortest-path cost on the currently passable network.
"""
from __future__ import annotations
import numpy as np
import networkx as nx
from .config import SimConfig
from .grid import Terrain


class RoadNetwork:
    def __init__(self, terrain: Terrain, cfg: SimConfig):
        self.terrain = terrain
        self.cfg = cfg
        self.n = terrain.size
        self.base_graph = self._build_grid_graph()
        self.graph = self.base_graph.copy()
        self._closed_edges = 0

    def _build_grid_graph(self) -> nx.Graph:
        g = nx.Graph()
        n = self.n
        for r in range(n):
            for c in range(n):
                g.add_node((r, c))
        # 4-connected road grid; base cost = 1 cell (minutes at base speed)
        minutes_per_cell = (self.cfg.cell_km / self.cfg.base_speed_kmh) * 60.0
        for r in range(n):
            for c in range(n):
                if c + 1 < n:
                    g.add_edge((r, c), (r, c + 1), base=minutes_per_cell)
                if r + 1 < n:
                    g.add_edge((r, c), (r + 1, c), base=minutes_per_cell)
        return g

    def update(self, water: np.ndarray):
        """Recompute edge weights / closures from the current flood depth."""
        cfg = self.cfg
        closed = 0
        for u, v, data in self.base_graph.edges(data=True):
            depth = max(water[u], water[v])
            if depth >= cfg.road_impassable_depth:
                if self.graph.has_edge(u, v):
                    self.graph.remove_edge(u, v)
                closed += 1
            else:
                # slowdown factor grows with depth up to the closure threshold
                slow = 1.0 + 6.0 * (depth / cfg.road_impassable_depth)
                self.graph.add_edge(u, v, weight=data["base"] * slow)
        self._closed_edges = closed

    def travel_time(self, src, dst):
        """Shortest-path travel time in minutes, or None if unreachable."""
        try:
            return nx.shortest_path_length(self.graph, src, dst, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def travel_times_from(self, src):
        """Dijkstra travel times from src to all reachable nodes."""
        try:
            return nx.single_source_dijkstra_path_length(self.graph, src, weight="weight")
        except nx.NodeNotFound:
            return {}

    def next_hop(self, src, dst):
        """First step on the shortest path from src toward dst (for agent movement)."""
        try:
            path = nx.shortest_path(self.graph, src, dst, weight="weight")
            return path[1] if len(path) > 1 else src
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    @property
    def closed_fraction(self):
        total = self.base_graph.number_of_edges()
        return self._closed_edges / total if total else 0.0
