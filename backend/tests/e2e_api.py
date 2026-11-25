"""
End-to-end API test for FloodResQ, run against a LIVE server (not pytest-collected).

It drives the same endpoints the React UI uses, in the same order a defence demo
would: sign in -> simulate each strategy -> compare -> recommend -> save a scenario
-> run it -> read persisted runs -> stream a run over the WebSocket -> reject bad
input and unauthenticated access.

Usage (server must already be running):
    python tests/e2e_api.py                      # defaults to http://localhost:8000
    python tests/e2e_api.py http://localhost:8001

Exit code 0 = every check passed; 1 = at least one failed.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
STRATEGIES = ["random", "nearest", "pop_proportional", "ai_optimised"]

_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _results.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def login(client: httpx.Client, user: str, pw: str) -> httpx.Response:
    return client.post("/api/auth/login", data={"username": user, "password": pw})


async def ws_run(token: str, payload: dict) -> dict:
    """Stream one full run over /ws/run and return a summary of what arrived."""
    url = BASE.replace("http", "ws", 1) + "/ws/run"
    summary = {"init": 0, "steps": 0, "done": None, "error": None}
    async with websockets.connect(url, max_size=None, open_timeout=30) as ws:
        await ws.send(json.dumps({**payload, "token": token}))
        async for raw in ws:
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "init":
                summary["init"] += 1
            elif t == "step":
                summary["steps"] += 1
            elif t == "done":
                summary["done"] = msg.get("kpis")
                break
            elif t == "error":
                summary["error"] = msg.get("message")
                break
    return summary


def main() -> int:
    print(f"FloodResQ E2E against {BASE}\n")
    t0 = time.time()
    client = httpx.Client(base_url=BASE, timeout=300)

    # ---------------------------------------------------------------- 1. service health & static UI
    print("1. Service health and served frontend")
    r = client.get("/api/health")
    check("health endpoint returns ok", r.status_code == 200 and r.json().get("status") == "ok", r.text[:80])
    r = client.get("/api/regions")
    ids = [x.get("id") for x in r.json()] if r.status_code == 200 else []
    check("regions list includes lokoja, makurdi, yenagoa", {"lokoja", "makurdi", "yenagoa"} <= set(ids), str(ids))
    r = client.get("/")
    check("root serves the built React app", r.status_code == 200 and "<div id=\"root\"" in r.text,
          f"status {r.status_code}")

    # ---------------------------------------------------------------- 2. authentication & RBAC
    print("\n2. Authentication and access control")
    r = login(client, "planner", "planner123")
    check("planner (coordinator) can sign in", r.status_code == 200, f"status {r.status_code}")
    planner_tok = r.json().get("access_token", "")
    check("planner token carries role=coordinator", r.json().get("role") == "coordinator")
    r = login(client, "admin", "admin123")
    check("admin can sign in and has role=admin", r.status_code == 200 and r.json().get("role") == "admin")
    admin_tok = r.json().get("access_token", "")
    r = login(client, "planner", "wrong-password")
    check("wrong password is rejected with 401", r.status_code == 401, f"status {r.status_code}")
    r = client.get("/api/risk?region=lokoja")
    check("protected endpoint rejects anonymous request (401)", r.status_code == 401, f"status {r.status_code}")
    bad = {"Authorization": "Bearer not-a-real-token"}
    r = client.get("/api/auth/me", headers=bad)
    check("forged JWT is rejected (401)", r.status_code == 401, f"status {r.status_code}")
    H = {"Authorization": f"Bearer {planner_tok}"}
    r = client.get("/api/auth/me", headers=H)
    check("/api/auth/me returns the signed-in user", r.status_code == 200 and r.json().get("username") == "planner")

    # new self-registration, then duplicate must fail
    new_user = f"e2e_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={"username": new_user, "password": "defence2026", "role": "coordinator"})
    check("self-registration issues a token", r.status_code == 200 and r.json().get("access_token"), f"status {r.status_code}")
    r = client.post("/api/auth/register", json={"username": new_user, "password": "defence2026"})
    check("duplicate registration is rejected (400)", r.status_code == 400, f"status {r.status_code}")

    # ---------------------------------------------------------------- 3. risk model (Objective 3)
    print("\n3. ML flood-risk model")
    r = client.get("/api/risk?region=lokoja", headers=H)
    body = r.json() if r.status_code == 200 else {}
    auc = (body.get("metrics") or {}).get("roc_auc") if isinstance(body.get("metrics"), dict) else None
    check("risk surface returns cells", r.status_code == 200 and len(body.get("cells", [])) > 0,
          f"status {r.status_code}, cells {len(body.get('cells', []))}")
    check("risk cells carry a 0..1 score", all(0 <= c["risk"] <= 1 for c in body.get("cells", [])))
    check("risk model reports metrics", body.get("metrics") is not None, f"roc_auc={auc}")

    # ---------------------------------------------------------------- 4. simulation, every strategy (Obj 1, 2)
    print("\n4. Simulation under every strategy")
    kpi_by_strat = {}
    for strat in STRATEGIES:
        r = client.post("/api/simulate", headers=H, json={"region": "lokoja", "strategy": strat, "seed": 42})
        ok = r.status_code == 200
        d = r.json() if ok else {}
        k = d.get("kpis", {})
        kpi_by_strat[strat] = k
        check(f"simulate[{strat}] completes and finishes", ok and d.get("finished") is True,
              f"status {r.status_code}")
        check(f"simulate[{strat}] KPIs are bounded",
              ok and 0 <= k.get("coverage_pct", -1) <= 100 and 0 <= k.get("utilisation_pct", -1) <= 100
              and k.get("casualties", -1) >= 0 and k.get("rescued", -1) >= 0,
              f"coverage {k.get('coverage_pct')}%, casualties {k.get('casualties')}")
        pc = d.get("population_counts", {})
        check(f"simulate[{strat}] agents are accounted for", sum(pc.values()) > 0 and "casualty" in pc,
              f"{sum(pc.values())} people")

    r1 = client.post("/api/simulate", headers=H, json={"region": "lokoja", "strategy": "ai_optimised", "seed": 42})
    r2 = client.post("/api/simulate", headers=H, json={"region": "lokoja", "strategy": "ai_optimised", "seed": 42})
    check("same seed gives identical KPIs over the API (reproducibility)",
          r1.json().get("kpis") == r2.json().get("kpis"))

    # ---------------------------------------------------------------- 5. compare & recommend (Obj 2, 5)
    print("\n5. Strategy comparison and AI recommendation")
    r = client.post("/api/compare", headers=H, json={"region": "lokoja", "flood_intensity": 0.6,
                                                    "rainfall_mm": 60, "seeds": 2})
    cmp_ = r.json() if r.status_code == 200 else {}
    check("compare returns all four strategies", r.status_code == 200 and set(STRATEGIES) <= set(cmp_),
          f"status {r.status_code}")
    check("baseline (random) averts 0 casualties vs itself",
          cmp_.get("random", {}).get("casualties_averted") == 0)
    r = client.post("/api/compare", headers=H, json={"setup": "experiment", "seeds": 2})
    check("compare works in the Chapter 4 'experiment' setup",
          r.status_code == 200 and set(STRATEGIES) <= set(r.json()), f"status {r.status_code}")
    r = client.post("/api/recommend", headers=H, json={"region": "lokoja", "seeds": 2})
    rec = r.json() if r.status_code == 200 else {}
    check("recommend names a best strategy with a recommendation text",
          rec.get("best") in STRATEGIES and bool(rec.get("recommendation")), f"best={rec.get('best')}")

    # ---------------------------------------------------------------- 6. persistence (ERD)
    print("\n6. Scenario persistence (ERD)")
    name = f"E2E scenario {uuid.uuid4().hex[:6]}"
    r = client.post("/api/scenarios", headers=H, json={"name": name, "region": "lokoja", "flood_intensity": 0.7,
                                                      "rainfall_mm": 90, "n_responder_units": 20, "n_ambulances": 10})
    check("save scenario returns an id", r.status_code == 200 and r.json().get("id"), f"status {r.status_code}")
    sid = r.json().get("id", "")
    r = client.get("/api/scenarios", headers=H)
    names = [s["name"] for s in r.json()] if r.status_code == 200 else []
    check("saved scenario appears in the planner's list", name in names)
    r = client.post(f"/api/scenarios/{sid}/run", headers=H, json={"strategy": "ai_optimised", "seed": 7})
    run_ok = r.status_code == 200 and r.json().get("run_id")
    check("running a saved scenario persists a run with KPIs", run_ok and r.json().get("kpis"),
          f"status {r.status_code}")
    r = client.get(f"/api/scenarios/{sid}/runs", headers=H)
    runs = r.json() if r.status_code == 200 else []
    check("the persisted run is listed with its metrics",
          len(runs) == 1 and runs[0].get("kpis") is not None, f"{len(runs)} run(s)")
    r = client.post("/api/scenarios/does-not-exist/run", headers=H, json={"strategy": "random", "seed": 1})
    check("running an unknown scenario returns 404", r.status_code == 404, f"status {r.status_code}")
    r = client.get("/api/scenarios", headers={"Authorization": f"Bearer {admin_tok}"})
    check("admin can see scenarios (RBAC: admin sees all)", r.status_code == 200)

    # ---------------------------------------------------------------- 7. live WebSocket stream (Obj 4)
    print("\n7. Live WebSocket streaming")
    try:
        s = asyncio.run(ws_run(planner_tok, {"region": "lokoja", "strategy": "ai_optimised", "seed": 42,
                                             "flood_intensity": 0.6, "rainfall_mm": 60, "delay": 0}))
        check("WebSocket sends init, then steps, then done",
              s["init"] == 1 and s["steps"] > 10 and s["done"] is not None, f"steps={s['steps']}")
        check("WebSocket 'done' carries KPIs", bool(s["done"]) and "coverage_pct" in s["done"])
        s2 = asyncio.run(ws_run("forged.token.value", {"region": "lokoja", "delay": 0}))
        check("WebSocket rejects a forged token", s2["error"] and "Unauthorised" in s2["error"],
              str(s2["error"])[:60])
    except Exception as e:  # network/handshake failure should be a visible FAIL, not a crash
        check("WebSocket streaming works", False, f"{type(e).__name__}: {e}")

    # ---------------------------------------------------------------- 8. input validation
    print("\n8. Input validation")
    r = client.post("/api/simulate", headers=H, json={"flood_intensity": 5.0})
    check("out-of-range flood_intensity rejected (422)", r.status_code == 422, f"status {r.status_code}")
    r = client.post("/api/simulate", headers=H, json={"setup": "something-else"})
    check("unknown setup name rejected (422)", r.status_code == 422, f"status {r.status_code}")
    r = client.post("/api/auth/register", json={"username": "x", "password": "123"})
    check("too-short username and password rejected (422)", r.status_code == 422, f"status {r.status_code}")

    # ---------------------------------------------------------------- summary
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    failed = [n for n, ok, _ in _results if not ok]
    print(f"\n{passed}/{total} checks passed in {time.time() - t0:.1f}s")
    if failed:
        print("FAILED:")
        for n in failed:
            print("  -", n)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
