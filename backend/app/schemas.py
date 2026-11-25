"""Pydantic request/response schemas for the API."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, Field


SetupName = Literal["experiment", "live"]


class ScenarioRequest(BaseModel):
    region: str = "lokoja"
    flood_intensity: float = Field(0.6, ge=0.1, le=1.0)
    rainfall_mm: float = Field(60.0, ge=10.0, le=200.0)
    strategy: str = "ai_optimised"
    seed: int = 42
    use_risk: bool = True
    setup: SetupName = "live"
    n_responder_units: int | None = None
    n_ambulances: int | None = None


class CompareRequest(BaseModel):
    region: str = "lokoja"
    flood_intensity: float = 0.6
    rainfall_mm: float = 60.0
    seeds: int = Field(6, ge=1, le=30)
    setup: SetupName = "live"


# ---- auth ----
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=6, max_length=128)
    role: str = "coordinator"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# ---- persistence ----
class SaveScenarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    region: str = "lokoja"
    flood_intensity: float = Field(0.6, ge=0.1, le=1.0)
    rainfall_mm: float = Field(60.0, ge=10.0, le=200.0)
    n_responder_units: int = 20
    n_ambulances: int = 10


class RunScenarioRequest(BaseModel):
    strategy: str = "ai_optimised"
    seed: int = 42
    persist_agents: bool = False
