"""
Database layer — SQLAlchemy engine, session and ORM models matching the ERD.

Uses SQLite for the MVP (file: flood_sim.db). The schema is Postgres/PostGIS-ready:
swap the engine URL and the GeoLayer.geometry column type for a real deployment.
"""
from __future__ import annotations
import os
import uuid
import datetime as dt

from sqlalchemy import (create_engine, String, Integer, Float, DateTime, ForeignKey, Text)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker)

DB_PATH = os.environ.get("FLOOD_DB", os.path.join(os.path.dirname(__file__), "..", "flood_sim.db"))
engine = create_engine(f"sqlite:///{os.path.abspath(DB_PATH)}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _uid() -> str:
    return uuid.uuid4().hex


def now() -> dt.datetime:
    return dt.datetime.utcnow()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="coordinator")  # coordinator|researcher|admin
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(60))
    flood_intensity: Mapped[float] = mapped_column(Float)
    rainfall_mm: Mapped[float] = mapped_column(Float)
    n_responder_units: Mapped[int] = mapped_column(Integer, default=20)
    n_ambulances: Mapped[int] = mapped_column(Integer, default=10)
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

    runs: Mapped[list["SimulationRun"]] = relationship(back_populates="scenario", cascade="all, delete-orphan")
    resources: Mapped[list["Resource"]] = relationship(cascade="all, delete-orphan")
    hospitals: Mapped[list["Hospital"]] = relationship(cascade="all, delete-orphan")
    layers: Mapped[list["GeoLayer"]] = relationship(cascade="all, delete-orphan")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    scenario_id: Mapped[str] = mapped_column(String(32), ForeignKey("scenarios.id"))
    strategy: Mapped[str] = mapped_column(String(30))
    seed: Mapped[int] = mapped_column(Integer)
    steps: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="finished")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

    scenario: Mapped["Scenario"] = relationship(back_populates="runs")
    metric: Mapped["ResultMetric"] = relationship(back_populates="run", uselist=False, cascade="all, delete-orphan")


class ResultMetric(Base):
    __tablename__ = "result_metrics"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("simulation_runs.id"))
    avg_response_time: Mapped[float] = mapped_column(Float)
    coverage_pct: Mapped[float] = mapped_column(Float)
    casualties: Mapped[int] = mapped_column(Integer)
    rescued: Mapped[int] = mapped_column(Integer)
    utilisation_pct: Mapped[float] = mapped_column(Float)

    run: Mapped["SimulationRun"] = relationship(back_populates="metric")


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    scenario_id: Mapped[str] = mapped_column(String(32), ForeignKey("scenarios.id"))
    type: Mapped[str] = mapped_column(String(20))
    depot_lat: Mapped[float] = mapped_column(Float)
    depot_lng: Mapped[float] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(Integer)
    speed_kmh: Mapped[float] = mapped_column(Float, default=50.0)


class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    scenario_id: Mapped[str] = mapped_column(String(32), ForeignKey("scenarios.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    beds: Mapped[int] = mapped_column(Integer)


class GeoLayer(Base):
    __tablename__ = "geo_layers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    scenario_id: Mapped[str] = mapped_column(String(32), ForeignKey("scenarios.id"))
    layer_type: Mapped[str] = mapped_column(String(30))
    geometry: Mapped[str] = mapped_column(Text)  # GeoJSON text (PostGIS GEOMETRY in production)


class AgentState(Base):
    __tablename__ = "agent_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("simulation_runs.id"))
    step: Mapped[int] = mapped_column(Integer)
    agent_type: Mapped[str] = mapped_column(String(20))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
