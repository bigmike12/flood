# FloodResQ — AI-Driven Flood Disaster Response Simulation Platform

An interactive, full-stack platform that simulates a flood disaster in a Nigerian urban
region and uses AI optimisation to decide how limited emergency resources (responders,
ambulances, hospital/shelter capacity) should be allocated. Emergency planners can rehearse
and compare response strategies as *what-if* scenarios **before** a disaster.

### Data: what is real vs. synthetic (read this)

The map **basemap** (OpenStreetMap tiles) and the **region coordinates** (Lokoja,
Makurdi, Yenagoa) are real. Everything the simulation computes on is **synthetically
generated** and positioned over those coordinates: the terrain/DEM, the road graph used
for routing (a grid, not the OSM roads shown), the population, and the facilities. No
historical flood data is ingested, and the ML model is trained on labels produced by the
simulation itself. FloodResQ is a **planning sandbox**, not a data-driven model of Lokoja.
Ingesting a real DEM and the real OSM road network is the primary future-work item.

### Optimiser

The resource allocation is a constrained assignment problem, solved to optimality with the
**Hungarian algorithm** (SciPy, default). A **Google OR-Tools CP-SAT** solver is also
implemented and selectable with `FLOOD_SOLVER=ortools`; both reach the same optimal
objective (verified in `tests/test_core.py::test_ortools_matches_hungarian`).

Final Year Project — Jonathan Micheal Chukwuma (2024/A/CSC/0006), Department of Computer
Science, MIVA Open University. Supervisor: Abiodun Mustapha.

---

## Stack

- **Backend:** Python 3.11, FastAPI, WebSockets, NumPy, SciPy, scikit-learn, NetworkX,
  SQLAlchemy (SQLite; PostGIS-ready), JWT auth.
- **Frontend:** React 18 + TypeScript + Vite, react-leaflet (map), Recharts (charts).
- **Auth & security:** JWT login, PBKDF2 password hashing, role-based access
  (coordinator / researcher / admin), request rate limiting, Pydantic input validation.
- **Persistence (ERD):** Scenario, SimulationRun, ResultMetric, Resource, Hospital,
  GeoLayer, AgentState, User.

## Objectives → code

| # | Objective | Where |
|---|-----------|-------|
| 1 | Agent-based flood + population + responders + hospitals + roads | `backend/app/{grid,flood,roads,agents,model}.py` |
| 2 | AI resource-allocation optimiser + 4 strategies | `backend/app/optimizer.py` |
| 3 | ML flood-risk model + scenario generation | `backend/app/ml_risk.py`, `scenario.py` |
| 4 | Interactive web platform (React + map + dashboards + login) | `backend/app/main.py`, `frontend/src/**` |
| 5 | Evaluation: experiments, KPIs, benchmarking | `backend/experiments/run_experiments.py`, `backend/tests/` |

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # optional
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The database (`flood_sim.db`) and two demo users are created automatically on first run:

- **planner / planner123**  (coordinator)
- **admin / admin123**  (admin — sees all scenarios)

### 2. Frontend

The backend serves a **pre-built** React app from `frontend/dist`, so opening
**http://localhost:8000** just works.

To develop the frontend live:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies API/WS to :8000
# npm run build    # rebuilds frontend/dist that the backend serves
```

## Using the platform (defence demo — ~5 minutes)

1. Sign in (planner / planner123).
2. **Setup = Report setup (Chapter 4 numbers)** is the default. Press **Run 30-seed comparison**
   — the chart and table reproduce the evaluation table exactly. *(Obj 5)*
3. **Setup = Live map** — pick a **region** (each has distinct terrain, so results differ).
4. **Toggle risk heat-map** — the Random Forest scores cells by flood susceptibility
   (ROC-AUC ≈ 0.84 on a held-out split; lowest-elevation alone scores about the same).
   It weights where residents live; it does not change the flood. *(Objective 3)*
5. Set strategy **Random**, press **Run**; watch the flood spread, roads close, casualties
   rise. Reset, switch to **AI-optimised**, run again. Single seeds vary, so compare over
   seeds (step 2) rather than trusting one run. *(Obj 1, 2, 4)*
6. **Get AI recommendation** — the system compares strategies and states the best one.
7. **Save scenario to database**, then click it under *Saved scenarios* to run and persist
   a result — demonstrates the ERD persistence. *(Objective 4 / data layer)*

## Evaluation figures (Chapter 4)

```bash
cd backend
python -m experiments.run_experiments --seeds 30
# -> experiments/results/{summary.json, runs.csv, fig_response_time.png, fig_coverage.png, fig_casualties.png}
```

30-seed result (mean over seeds 0–29, Report setup):

| Strategy | Coverage | Casualties | Casualties averted vs random |
|---|---|---|---|
| Random | 44.1% | 85.2 | — |
| Nearest-depot | 50.5% | 78.1 | 7.1 |
| Population-proportional | 50.3% | 77.1 | 8.1 |
| AI-optimised | 51.0% | 76.9 | 8.3 |

AI-optimised has the highest coverage and fewest casualties, but the margin over the greedy
nearest-depot and population-proportional heuristics is small. Mean response time is 46.7 min
for AI-optimised vs 47.5 min for random. The ML risk model scores ROC-AUC ≈ 0.84 on its
held-out split, about the same as ranking cells by lowest elevation (0.84). On six unseen terrains
the forest scores 0.87–0.89 against 0.82–0.84 for elevation. See `backend/experiments/ml_validation.py`
and `backend/experiments/results/ml_validation.json`.

## Tests

```bash
cd backend && pytest -q
```

## Security notes

Auth is real: JWT tokens, hashed passwords, role checks, rate limiting, validated input,
and WebSocket token auth. For production, set `FLOOD_SECRET` and `FLOOD_DB` as environment
secrets and serve over HTTPS/TLS behind a reverse proxy.

## Limitations & future work

Synthetic-but-plausible DEM/parameters (documented in `config.py`); cellular-automaton
flood model (not full hydrodynamics); lightweight agent scheduler (Mesa/OR-Tools can be
swapped at the marked interfaces). Future: live rainfall/river-gauge data, a full
hydrodynamic solver, empirically grounded behaviour, RL dispatch, and field calibration.
