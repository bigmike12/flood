"""
Key performance indicators for evaluating a response strategy (Objective 5).

  - response_time   : mean minutes from a rescue request to the rescue
  - coverage        : share of people who requested help who were rescued
  - casualties      : people who were not rescued in time
  - utilisation     : share of responder time spent actively serving demands
"""
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean
from .agents import RESCUED, CASUALTY, AWAITING


@dataclass
class KPIs:
    mean_response_time: float
    coverage_pct: float
    casualties: int
    rescued: int
    total_requests: int
    utilisation_pct: float
    unmet: int

    def to_dict(self):
        return {
            "mean_response_time": round(self.mean_response_time, 2),
            "coverage_pct": round(self.coverage_pct, 1),
            "casualties": self.casualties,
            "rescued": self.rescued,
            "total_requests": self.total_requests,
            "utilisation_pct": round(self.utilisation_pct, 1),
            "unmet": self.unmet,
        }


def compute_kpis(population, responders, elapsed_minutes):
    requesters = [p for p in population if p.response_time is not None or p.state in (AWAITING, RESCUED, CASUALTY)]
    rescued = [p for p in population if p.state == RESCUED]
    casualties = [p for p in population if p.state == CASUALTY]
    unmet = [p for p in population if p.state == AWAITING]

    rts = [p.response_time for p in rescued if p.response_time is not None]
    mean_rt = mean(rts) if rts else 0.0

    total_requests = len(requesters)
    coverage = 100.0 * len(rescued) / total_requests if total_requests else 0.0

    if responders and elapsed_minutes > 0:
        busy = sum(min(r.distance_min, elapsed_minutes) for r in responders)
        util = 100.0 * busy / (len(responders) * elapsed_minutes)
    else:
        util = 0.0

    return KPIs(
        mean_response_time=mean_rt,
        coverage_pct=coverage,
        casualties=len(casualties),
        rescued=len(rescued),
        total_requests=total_requests,
        utilisation_pct=min(util, 100.0),
        unmet=len(unmet),
    )
