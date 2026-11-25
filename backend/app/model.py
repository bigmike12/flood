"""
FloodResponseModel — the agent-based simulation that ties everything together
(Objective 1). One step of the model:

  1. advance the flood (cellular automaton);
  2. update road accessibility from flood depth;
  3. population agents sense their risk and act (evacuate / request help);
  4. the optimiser assigns idle responder units to open demands (Objective 2);
  5. responder/ambulance agents travel and perform rescues;
  6. hospital load and KPIs are updated (Objective 5).

The run is deterministic given the seed, so results are reproducible.
"""
from __future__ import annotations
import numpy as np

from .config import SimConfig
from .grid import Terrain
from .flood import FloodModel
from .roads import RoadNetwork
from . import agents as A
from . import optimizer as OPT
from .metrics import compute_kpis


class FloodResponseModel:
    def __init__(self, cfg: SimConfig, terrain: Terrain | None = None, risk_surface=None):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.terrain = terrain or Terrain(cfg.grid_size, cfg.cell_km, cfg.seed)
        self.flood = FloodModel(self.terrain, cfg)
        self.roads = RoadNetwork(self.terrain, cfg)
        self.risk_surface = risk_surface     # optional ML risk grid (0..1) for placement
        self.minute = 0.0
        self.step_i = 0
        self.finished = False

        self._place_infrastructure()
        self._place_population()
        self.roads.update(self.flood.water)

    # ------------------------------------------------------------------ setup
    def _low_cells(self, k, avoid_river=False):
        """Pick k distinct cells, biased toward higher ground (for depots/hospitals)."""
        elev = self.terrain.elevation
        n = self.cfg.grid_size
        flat = [(r, c) for r in range(n) for c in range(n)]
        # higher ground = safer siting for infrastructure
        flat.sort(key=lambda rc: -elev[rc])
        pool = flat[: max(k * 12, 12)]
        idx = self.rng.choice(len(pool), size=k, replace=False)
        return [pool[i] for i in idx]

    def _place_infrastructure(self):
        cfg = self.cfg
        depots = self._low_cells(cfg.n_depots)
        self.depots = depots
        self.responders = []
        uid = 0
        # rescue units spread across depots
        for i in range(cfg.n_responder_units):
            d = depots[i % len(depots)]
            self.responders.append(A.ResponderAgent(uid=uid, pos=d, depot=d,
                                                    kind="responder", capacity=cfg.responder_capacity))
            uid += 1
        for i in range(cfg.n_ambulances):
            d = depots[i % len(depots)]
            self.responders.append(A.ResponderAgent(uid=uid, pos=d, depot=d,
                                                    kind="ambulance", capacity=1))
            uid += 1
        hosp_cells = self._low_cells(cfg.n_hospitals)
        self.hospitals = [A.HospitalAgent(uid=i, pos=hosp_cells[i], beds=cfg.hospital_beds)
                          for i in range(cfg.n_hospitals)]

    def _place_population(self):
        cfg = self.cfg
        n = cfg.grid_size
        # people live preferentially in flood-prone low ground near the river
        elev = self.terrain.elevation
        prob = np.exp(-(elev - elev.min()) / 16.0)
        if self.risk_surface is not None:
            prob = prob * (0.5 + 0.7 * self.risk_surface)
        prob = prob / prob.sum()
        flat_idx = self.rng.choice(n * n, size=cfg.n_population, p=prob.ravel())
        self.population = []
        for uid, fi in enumerate(flat_idx):
            r, c = divmod(int(fi), n)
            sev = 1.0 + float(self.rng.random() < 0.2) * 1.5   # 20% high-vulnerability
            self.population.append(A.PopulationAgent(uid=uid, pos=(r, c), severity=sev))
        self._pop_by_uid = {p.uid: p for p in self.population}

    # ------------------------------------------------------------------- step
    def step(self):
        if self.finished:
            return
        cfg = self.cfg
        self.flood.step()
        if self.step_i % cfg.road_update_interval == 0:
            self.roads.update(self.flood.water)

        water = self.flood.water
        self._update_population(water)
        self._assign_and_move(water)

        self.minute += cfg.minutes_per_step
        self.step_i += 1
        if self.step_i >= cfg.total_steps:
            self.finished = True

    def _update_population(self, water):
        cfg = self.cfg
        for p in self.population:
            if p.state in (A.RESCUED, A.CASUALTY):
                continue
            depth = water[p.pos]
            if p.state == A.SAFE and depth >= cfg.evacuate_depth:
                p.state = A.AT_RISK
                p._rolled = False
            if p.state == A.AT_RISK:
                # one-time decision: call for help, or attempt to self-evacuate
                if not getattr(p, "_rolled", False):
                    p._rolled = True
                    # deeper water makes a resident more likely to need rescue
                    prob = cfg.help_request_prob + 0.4 * min(depth / cfg.casualty_depth, 1.0)
                    if self.rng.random() < min(prob, 0.95):
                        p.state = A.AWAITING
                        p.wait_steps = 0
                        p.request_minute = self.minute
                # residents in mortal-depth water who never got help are in danger
                if p.state == A.AT_RISK and depth >= cfg.casualty_depth:
                    p.state = A.AWAITING
                    p.wait_steps = 0
                    p.request_minute = self.minute
            if p.state == A.AWAITING:
                p.wait_steps += 1
                # vulnerable (high-severity) people have a shorter survival window,
                # so a strategy that reaches them first (severity-weighted) saves more.
                deadline = cfg.max_wait_steps
                if p.severity > 1.0:
                    deadline = int(cfg.max_wait_steps * cfg.vulnerable_deadline_factor)
                deep = depth >= cfg.casualty_depth
                if deep and p.wait_steps > int(deadline * 0.7):
                    p.state = A.CASUALTY
                elif p.wait_steps > deadline:
                    p.state = A.CASUALTY

    def _open_demands(self):
        return [p for p in self.population
                if p.state == A.AWAITING and getattr(p, "assigned_to", None) is None]

    def _assign_and_move(self, water):
        cfg = self.cfg
        # 1) assign idle units to open demands via the chosen strategy
        idle = [r for r in self.responders if r.state == A.IDLE]
        demands = self._open_demands()
        if idle and demands:
            # annotate each demand with how close it is to its survival deadline
            for p in demands:
                deadline = cfg.max_wait_steps
                if p.severity > 1.0:
                    deadline = int(cfg.max_wait_steps * cfg.vulnerable_deadline_factor)
                p.urgency = min(p.wait_steps / max(deadline, 1), 1.5)
            travel_from = self.roads.travel_times_from
            assign = OPT.allocate(cfg.strategy, idle, demands, travel_from,
                                  self.rng, cfg.severity_weight, cfg.rescue_radius)
            for ui, dj in assign.items():
                unit = idle[ui]
                dem = demands[dj]
                t = self.roads.travel_time(unit.pos, dem.pos)
                if t is None:
                    continue
                unit.state = A.EN_ROUTE
                unit.target = dem.uid
                unit._remaining = t          # minutes to reach the demand
                unit._phase = "to_demand"
                dem.assigned_to = unit.uid

        # 2) advance en-route / returning units
        for r in self.responders:
            if r.state == A.IDLE:
                continue
            r._remaining -= cfg.minutes_per_step
            r.distance_min += cfg.minutes_per_step
            if r._remaining > 0:
                continue
            if r._phase == "to_demand":
                self._perform_rescue(r)
            elif r._phase == "to_hospital":
                # ambulance has offloaded; now free at the hospital location
                r.state = A.IDLE
                r.target = None
            else:
                r.state = A.IDLE
                r.target = None

    def _perform_rescue(self, unit):
        cfg = self.cfg
        p = self._pop_by_uid.get(unit.target)
        rescued_here = []
        if p is not None and p.state == A.AWAITING:
            self._rescue_person(p, unit)
            rescued_here.append(p)
            # cluster rescue: also take nearby awaiting people up to capacity
            r0, c0 = p.pos
            nearby = [q for q in self.population
                      if q.state == A.AWAITING and getattr(q, "assigned_to", None) in (None, unit.uid)
                      and abs(q.pos[0] - r0) <= cfg.rescue_radius
                      and abs(q.pos[1] - c0) <= cfg.rescue_radius]
            nearby.sort(key=lambda q: -q.severity)
            for q in nearby[: unit.capacity - 1]:
                self._rescue_person(q, unit)
                rescued_here.append(q)
        unit.pos = p.pos if p else unit.pos
        if unit.kind == "ambulance" and rescued_here:
            # ambulance must offload at the nearest reachable hospital before reuse
            h = min(self.hospitals, key=lambda h: abs(h.pos[0] - unit.pos[0]) + abs(h.pos[1] - unit.pos[1]))
            t_h = self.roads.travel_time(unit.pos, h.pos)
            unit._phase = "to_hospital"
            unit._remaining = t_h if t_h is not None else cfg.minutes_per_step
            unit.pos = h.pos
            unit.state = A.RETURNING
        else:
            # rescue units chain: immediately available at the rescue location
            unit.state = A.IDLE
            unit.target = None

    def _rescue_person(self, q, unit):
        q.state = A.RESCUED
        q.response_time = self.minute - getattr(q, "request_minute", self.minute)
        if unit.kind == "ambulance":
            for h in sorted(self.hospitals,
                            key=lambda h: abs(h.pos[0] - q.pos[0]) + abs(h.pos[1] - q.pos[1])):
                if h.free > 0:
                    h.occupied += 1
                    break

    # ----------------------------------------------------------------- output
    def kpis(self):
        return compute_kpis(self.population, self.responders, max(self.minute, 1e-9))

    def run(self):
        while not self.finished:
            self.step()
        return self.kpis()

    def snapshot(self, downsample=1):
        """Compact state for streaming to the frontend."""
        water = self.flood.depth_grid()
        n = self.cfg.grid_size
        # downsample the flood grid for transport
        step = max(1, downsample)
        flood_cells = []
        for r in range(0, n, step):
            for c in range(0, n, step):
                d = float(water[r, c])
                if d > 0:
                    lat, lng = self.terrain.cell_to_latlng(r, c)
                    flood_cells.append({"lat": round(lat, 5), "lng": round(lng, 5), "depth": round(d, 2)})
        pop_counts = {}
        people = []
        for p in self.population:
            pop_counts[p.state] = pop_counts.get(p.state, 0) + 1
            lat, lng = self.terrain.cell_to_latlng(*p.pos)
            people.append({"lat": round(lat, 5), "lng": round(lng, 5), "state": p.state})
        units = []
        for r in self.responders:
            lat, lng = self.terrain.cell_to_latlng(*r.pos)
            units.append({"lat": round(lat, 5), "lng": round(lng, 5), "kind": r.kind, "state": r.state})
        return {
            "step": self.step_i,
            "minute": round(self.minute, 1),
            "flood": flood_cells,
            "people": people,
            "population_counts": pop_counts,
            "units": units,
            "hospitals": [{"lat": self.terrain.cell_to_latlng(*h.pos)[0],
                           "lng": self.terrain.cell_to_latlng(*h.pos)[1],
                           "free": h.free, "beds": h.beds} for h in self.hospitals],
            "roads_closed_pct": round(100 * self.roads.closed_fraction, 1),
            "flooded_pct": round(100 * self.flood.flooded_fraction(), 1),
            "kpis": self.kpis().to_dict(),
            "finished": self.finished,
        }
