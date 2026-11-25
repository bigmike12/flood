"""
Central configuration for the flood response simulation platform.

EVERY tunable / synthetic parameter lives here so it can be defended and
calibrated in one place. Values marked (SYNTHETIC) are plausible placeholders
derived from published NEMA/NIHSA/World Bank figures, not fitted to operational
ground-truth data. See Chapter 3 (Limitations) of the project report.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict


@dataclass
class SimConfig:
    # ---- grid / terrain ----
    grid_size: int = 40                 # cells per side (40x40 = 1600 cells)
    cell_km: float = 0.5                # (SYNTHETIC) each cell ~0.5 km
    seed: int = 42                      # deterministic runs

    # ---- flood cellular automaton ----
    flow_coeff: float = 0.25            # alpha: fraction of head difference that flows per step
    rainfall_mm: float = 60.0           # (SYNTHETIC) driving rainfall per storm step (mm)
    flood_intensity: float = 0.6        # 0..1 peak severity multiplier
    rain_steps: int = 25                # steps during which rain falls
    total_steps: int = 60              # total simulation steps
    minutes_per_step: float = 3.0       # (SYNTHETIC) wall-clock minutes each step represents
    road_update_interval: int = 2       # recompute road accessibility every N steps (perf)
    min_flood_depth: float = 0.05       # m, below this a cell is treated as dry

    # ---- roads ----
    road_impassable_depth: float = 0.35  # m, depth above which a road edge is closed (Pregnolato-style)
    base_speed_kmh: float = 50.0         # responder speed on open roads

    # ---- population ----
    n_population: int = 300             # (SYNTHETIC) number of population agents
    evacuate_depth: float = 0.30        # m, depth at which a resident becomes at-risk
    casualty_depth: float = 1.30        # m, depth at which an unrescued resident is in mortal danger
    help_request_prob: float = 0.38     # one-time prob an at-risk resident calls for help
    max_wait_steps: int = 55            # steps awaiting rescue before becoming a casualty
    vulnerable_deadline_factor: float = 0.55  # vulnerable (high-severity) people have a shorter deadline
    rescue_radius: int = 2              # cells; a unit also rescues nearby awaiting people (cluster)

    # ---- responders / resources ----
    n_responder_units: int = 20         # (SYNTHETIC) rescue units available
    n_ambulances: int = 10
    responder_capacity: int = 4         # people a unit can carry per trip
    n_depots: int = 3
    n_hospitals: int = 3
    hospital_beds: int = 50             # beds per hospital

    # ---- optimisation ----
    strategy: str = "ai_optimised"      # random | nearest | pop_proportional | ai_optimised
    severity_weight: float = 2.5        # weight multiplier for high-severity demand

    def to_dict(self) -> Dict:
        return asdict(self)


# Region presets — flood-prone Nigerian urban areas (approx. centre coordinates).
REGIONS = {
    "lokoja": {"name": "Lokoja (Niger-Benue confluence)", "lat": 7.802, "lng": 6.744},
    "makurdi": {"name": "Makurdi (Benue)", "lat": 7.733, "lng": 8.521},
    "yenagoa": {"name": "Yenagoa (Bayelsa)", "lat": 4.921, "lng": 6.264},
    "lagos": {"name": "Lagos (Lagos)", "lat": 6.524, "lng": 3.379},
}

DEFAULT_REGION = "lokoja"
