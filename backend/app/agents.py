"""
Agents for the flood-response model.

A lightweight, Mesa-style agent design: each agent has a unique id, a grid
position and a state. Agent decision logic that needs global information (flood
depth, road network, the optimiser) is driven from FloodResponseModel.step so the
whole simulation stays deterministic and easy to reason about.

Agent types:
  PopulationAgent  — residents; state machine SAFE -> AT_RISK -> AWAITING_RESCUE
                     -> RESCUED / CASUALTY
  ResponderAgent   — rescue units that travel to demands and carry people out
  AmbulanceAgent   — like responders but deliver casualties to hospitals
  HospitalAgent    — fixed capacity that admits rescued/injured people
"""
from __future__ import annotations
from dataclasses import dataclass, field

# population states
SAFE = "safe"
AT_RISK = "at_risk"
AWAITING = "awaiting_rescue"
RESCUED = "rescued"
CASUALTY = "casualty"

# responder states
IDLE = "idle"
EN_ROUTE = "en_route"
RETURNING = "returning"


@dataclass
class PopulationAgent:
    uid: int
    pos: tuple            # (row, col)
    state: str = SAFE
    severity: float = 1.0     # 1 = normal, higher = more vulnerable/urgent
    wait_steps: int = 0       # steps spent awaiting rescue
    response_time: float | None = None  # minutes from request to rescue


@dataclass
class ResponderAgent:
    uid: int
    pos: tuple            # current cell
    depot: tuple          # home depot cell
    kind: str = "responder"   # "responder" or "ambulance"
    capacity: int = 3
    state: str = IDLE
    target: int | None = None   # uid of the population agent being served
    onboard: int = 0
    distance_min: float = 0.0   # minutes travelled (for utilisation)


@dataclass
class HospitalAgent:
    uid: int
    pos: tuple
    beds: int = 40
    occupied: int = 0

    @property
    def free(self):
        return max(0, self.beds - self.occupied)
