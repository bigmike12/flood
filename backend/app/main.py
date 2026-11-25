"""
FastAPI application: authentication, database persistence (ERD), the simulation
REST/WebSocket API, and (optionally) the served frontend.

Run:  uvicorn app.main:app --reload   (from the backend/ directory)
Default users are seeded on first start (see startup()).
"""
from __future__ import annotations
import asyncio
import os
import statistics as st

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .config import SimConfig, REGIONS
from .schemas import (ScenarioRequest, CompareRequest, RegisterRequest, TokenResponse,
                      SaveScenarioRequest, RunScenarioRequest)
from . import scenario as SC
from . import db as DB
from . import auth as AUTH

app = FastAPI(title="FloodResQ — AI-Driven Flood Disaster Response Simulation Platform", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STRATEGIES = ["random", "nearest", "pop_proportional", "ai_optimised"]
LABELS = {"random": "Random", "nearest": "Nearest-depot",
          "pop_proportional": "Population-proportional", "ai_optimised": "AI-optimised"}


def bootstrap():
    """Create tables and seed default users. Runs at import so tables exist for
    both uvicorn and the test client."""
    DB.init_db()
    with DB.SessionLocal() as s:
        if not s.query(DB.User).filter_by(username="admin").first():
            # Demo passwords are the defaults; set FLOOD_ADMIN_PASSWORD / FLOOD_PLANNER_PASSWORD
            # before the first start to seed production accounts with other passwords.
            s.add(DB.User(username="admin", role="admin",
                          password_hash=AUTH.hash_password(os.environ.get("FLOOD_ADMIN_PASSWORD", "admin123"))))
            s.add(DB.User(username="planner", role="coordinator",
                          password_hash=AUTH.hash_password(os.environ.get("FLOOD_PLANNER_PASSWORD", "planner123"))))
            s.commit()
    if not os.environ.get("FLOOD_SECRET"):
        import logging
        logging.getLogger("uvicorn.error").warning(
            "FLOOD_SECRET is not set: using the built-in development JWT secret. Set it before any public deployment.")


bootstrap()


# ================================================================ AUTH
@app.post("/api/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(DB.get_db)):
    AUTH.rate_limit("register", limit=10)
    if db.query(DB.User).filter_by(username=req.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    role = req.role if req.role in ("coordinator", "researcher") else "coordinator"
    user = DB.User(username=req.username, password_hash=AUTH.hash_password(req.password), role=role)
    db.add(user); db.commit(); db.refresh(user)
    return TokenResponse(access_token=AUTH.create_token(user), username=user.username, role=user.role)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(DB.get_db)):
    AUTH.rate_limit("login:" + form.username, limit=8)
    user = db.query(DB.User).filter_by(username=form.username).first()
    if not user or not AUTH.verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return TokenResponse(access_token=AUTH.create_token(user), username=user.username, role=user.role)


@app.get("/api/auth/me")
def me(user: DB.User = Depends(AUTH.get_current_user)):
    return {"username": user.username, "role": user.role, "id": user.id}


# ================================================================ REFERENCE
@app.get("/api/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/api/regions")
def regions():
    return SC.region_list()


@app.get("/api/risk")
def risk(region: str = "lokoja", seed: int = 42, user: DB.User = Depends(AUTH.get_current_user)):
    info = SC.risk_metrics()
    from .grid import Terrain
    reg = REGIONS.get(region, REGIONS["lokoja"])
    cfg = SimConfig(seed=seed)
    terrain = Terrain(cfg.grid_size, cfg.cell_km, seed, reg["lat"], reg["lng"], region_key=region)
    surf = SC._RISK.risk_surface(terrain)
    cells, n = [], cfg.grid_size
    for r in range(0, n, 2):
        for c in range(0, n, 2):
            lat, lng = terrain.cell_to_latlng(r, c)
            cells.append({"lat": round(lat, 5), "lng": round(lng, 5), "risk": round(float(surf[r, c]), 3)})
    return {**info, "cells": cells}


# ================================================================ SIMULATE / COMPARE
@app.post("/api/simulate")
def simulate(req: ScenarioRequest, user: DB.User = Depends(AUTH.get_current_user)):
    AUTH.rate_limit("sim:" + user.id, limit=40)
    over = {}
    if req.n_responder_units:
        over["n_responder_units"] = req.n_responder_units
    if req.n_ambulances:
        over["n_ambulances"] = req.n_ambulances
    m = SC.build_model(region=req.region, flood_intensity=req.flood_intensity,
                       rainfall_mm=req.rainfall_mm, strategy=req.strategy,
                       seed=req.seed, use_risk=req.use_risk, **over)
    m.run()
    return m.snapshot(downsample=2)


@app.post("/api/compare")
def compare(req: CompareRequest, user: DB.User = Depends(AUTH.get_current_user)):
    AUTH.rate_limit("cmp:" + user.id, limit=20)
    out = {}
    for strat in STRATEGIES:
        ks = [SC.build_model(region=req.region, flood_intensity=req.flood_intensity,
                             rainfall_mm=req.rainfall_mm, strategy=strat, seed=seed).run().to_dict()
              for seed in range(req.seeds)]
        out[strat] = {
            "label": LABELS[strat],
            "mean_response_time": round(st.mean(x["mean_response_time"] for x in ks), 1),
            "coverage_pct": round(st.mean(x["coverage_pct"] for x in ks), 1),
            "casualties": round(st.mean(x["casualties"] for x in ks), 1),
            "utilisation_pct": round(st.mean(x["utilisation_pct"] for x in ks), 1),
        }
    base = out["random"]["casualties"]
    for s in STRATEGIES:
        out[s]["casualties_averted"] = round(base - out[s]["casualties"], 1)
    return out


@app.post("/api/recommend")
def recommend(req: CompareRequest, user: DB.User = Depends(AUTH.get_current_user)):
    comp = compare(req, user)
    best = min(STRATEGIES, key=lambda s: comp[s]["casualties"])
    base, b = comp["random"], comp[min(STRATEGIES, key=lambda s: comp[s]["casualties"])]
    rt_gain = round(100 * (base["mean_response_time"] - b["mean_response_time"]) / max(base["mean_response_time"], 1e-6))
    text = (f"Recommended strategy: {b['label']}. Versus uncoordinated (random) dispatch it raises "
            f"demand coverage to {b['coverage_pct']}%, averts about {b['casualties_averted']} casualties "
            f"and cuts mean response time by ~{int(rt_gain)}%. Pre-position responders toward the "
            f"high-risk river corridor before onset.")
    return {"best": best, "label": b["label"], "recommendation": text, "comparison": comp}


# ================================================================ PERSISTENCE (ERD)
@app.post("/api/scenarios")
def save_scenario(req: SaveScenarioRequest, db: Session = Depends(DB.get_db),
                  user: DB.User = Depends(AUTH.get_current_user)):
    sc = DB.Scenario(name=req.name, region=req.region, flood_intensity=req.flood_intensity,
                     rainfall_mm=req.rainfall_mm, n_responder_units=req.n_responder_units,
                     n_ambulances=req.n_ambulances, owner_id=user.id)
    db.add(sc); db.flush()
    # persist the resource depots, hospitals and geo layers produced for this scenario
    m = SC.build_model(region=req.region, flood_intensity=req.flood_intensity,
                       rainfall_mm=req.rainfall_mm, seed=42,
                       n_responder_units=req.n_responder_units, n_ambulances=req.n_ambulances)
    for u in m.responders:
        lat, lng = m.terrain.cell_to_latlng(*u.depot)
        db.add(DB.Resource(scenario_id=sc.id, type=u.kind, depot_lat=lat, depot_lng=lng,
                           capacity=u.capacity, speed_kmh=m.cfg.base_speed_kmh))
    for h in m.hospitals:
        lat, lng = m.terrain.cell_to_latlng(*h.pos)
        db.add(DB.Hospital(scenario_id=sc.id, lat=lat, lng=lng, beds=h.beds))
    db.add(DB.GeoLayer(scenario_id=sc.id, layer_type="risk_surface", geometry="{}"))
    db.commit(); db.refresh(sc)
    return {"id": sc.id, "name": sc.name}


@app.get("/api/scenarios")
def list_scenarios(db: Session = Depends(DB.get_db), user: DB.User = Depends(AUTH.get_current_user)):
    q = db.query(DB.Scenario)
    if user.role != "admin":
        q = q.filter_by(owner_id=user.id)
    return [{"id": s.id, "name": s.name, "region": s.region, "flood_intensity": s.flood_intensity,
             "rainfall_mm": s.rainfall_mm, "n_responder_units": s.n_responder_units,
             "n_ambulances": s.n_ambulances, "runs": len(s.runs),
             "created_at": s.created_at.isoformat()} for s in q.order_by(DB.Scenario.created_at.desc()).all()]


@app.post("/api/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: str, req: RunScenarioRequest, db: Session = Depends(DB.get_db),
                 user: DB.User = Depends(AUTH.get_current_user)):
    sc = db.get(DB.Scenario, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    m = SC.build_model(region=sc.region, flood_intensity=sc.flood_intensity, rainfall_mm=sc.rainfall_mm,
                       strategy=req.strategy, seed=req.seed,
                       n_responder_units=sc.n_responder_units, n_ambulances=sc.n_ambulances)
    m.run()
    k = m.kpis().to_dict()
    run = DB.SimulationRun(scenario_id=sc.id, strategy=req.strategy, seed=req.seed,
                           steps=m.step_i, status="finished")
    db.add(run); db.flush()
    db.add(DB.ResultMetric(run_id=run.id, avg_response_time=k["mean_response_time"],
                           coverage_pct=k["coverage_pct"], casualties=k["casualties"],
                           rescued=k["rescued"], utilisation_pct=k["utilisation_pct"]))
    if req.persist_agents:
        for p in m.population[:400]:
            lat, lng = m.terrain.cell_to_latlng(*p.pos)
            db.add(DB.AgentState(run_id=run.id, step=m.step_i, agent_type="population",
                                 lat=lat, lng=lng, status=p.state))
    db.commit()
    return {"run_id": run.id, "kpis": k}


@app.get("/api/scenarios/{scenario_id}/runs")
def list_runs(scenario_id: str, db: Session = Depends(DB.get_db), user: DB.User = Depends(AUTH.get_current_user)):
    sc = db.get(DB.Scenario, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    out = []
    for r in sc.runs:
        mt = r.metric
        out.append({"run_id": r.id, "strategy": r.strategy, "seed": r.seed, "steps": r.steps,
                    "created_at": r.created_at.isoformat(),
                    "kpis": {"mean_response_time": mt.avg_response_time, "coverage_pct": mt.coverage_pct,
                             "casualties": mt.casualties, "rescued": mt.rescued,
                             "utilisation_pct": mt.utilisation_pct} if mt else None})
    return out


# ================================================================ WebSocket
@app.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    await ws.accept()
    try:
        cfg = await ws.receive_json()
        # authenticate: token supplied in the first message
        try:
            AUTH.decode_token(cfg.get("token", ""))
        except HTTPException:
            await ws.send_json({"type": "error", "message": "Unauthorised: please sign in again."})
            await ws.close()
            return
        over = {k: int(cfg[k]) for k in ("n_responder_units", "n_ambulances") if cfg.get(k)}
        model = SC.build_model(region=cfg.get("region", "lokoja"),
                               flood_intensity=float(cfg.get("flood_intensity", 0.6)),
                               rainfall_mm=float(cfg.get("rainfall_mm", 60.0)),
                               strategy=cfg.get("strategy", "ai_optimised"),
                               seed=int(cfg.get("seed", 42)),
                               use_risk=bool(cfg.get("use_risk", True)), **over)
        await ws.send_json({"type": "init", "bounds": model.terrain.bounds(),
                            "center": {"lat": model.terrain.center_lat, "lng": model.terrain.center_lng}})
        delay = float(cfg.get("delay", 0.12))
        while not model.finished:
            model.step()
            await ws.send_json({"type": "step", **model.snapshot(downsample=1)})
            await asyncio.sleep(delay)
        await ws.send_json({"type": "done", "kpis": model.kpis().to_dict()})
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ================================================================ frontend (built React app)
_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_DIST, "index.html"))
