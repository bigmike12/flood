# Deploying FloodResQ

One container serves both the API and the built React app.

## Build and run locally (verified)

```bash
cd flood-response-sim
docker build -t floodresq .
docker run -p 8000:8000 \
  -e FLOOD_SECRET="$(openssl rand -hex 32)" \
  -v floodresq-data:/data \
  floodresq
# open http://localhost:8000
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `FLOOD_SECRET` | **Yes for any public host** | Signs login tokens. If unset, the app uses a built-in development secret and logs a warning. |
| `FLOOD_ADMIN_PASSWORD` | Recommended | Password for the seeded `admin` account (default `admin123`). Applies only when the database is first created. |
| `FLOOD_PLANNER_PASSWORD` | Recommended | Password for the seeded `planner` account (default `planner123`). Same first-start rule. |
| `FLOOD_DB` | Set by image | SQLite path, `/data/flood_sim.db` in the container. Mount a volume on `/data`. |
| `PORT` | Set by host | Port to listen on (defaults to 8000). Render, Railway and similar hosts inject it. |

## Verified before writing this file

- `docker build` completes; image is about 1.1 GB (dominated by OR-Tools and SciPy).
- `tests/e2e_api.py` passes 42/42 against the container.
- Saved scenarios survive `docker restart` (the volume persists the database).
- Backend `pytest`: 6/6 passing.

## Before a public deployment

1. Set `FLOOD_SECRET` to a random value (never commit it).
2. Set `FLOOD_ADMIN_PASSWORD` and `FLOOD_PLANNER_PASSWORD`. The README lists the default demo passwords publicly, so do not leave them in place on a public URL.
3. Serve over HTTPS. The host usually provides this. Browsers need `wss://` for the live stream, and the app already switches to it on HTTPS.
4. Known limitations (acceptable for a demo, not for production):
   - CORS allows any origin (`allow_origins=["*"]`).
   - `POST /api/scenarios/{id}/run` does not check that the caller owns the scenario, so any signed-in user can run any scenario.
   - Rate limiting is in-memory, so it resets on restart and is not shared between instances.
   - SQLite supports a single writer; keep one instance.

## Hosting

No host has been chosen yet. Any container host works (Render, Railway, Fly.io, a VPS). The steps are the same: point the host at this repository's `Dockerfile`, add a persistent disk mounted at `/data`, and set the variables above.
