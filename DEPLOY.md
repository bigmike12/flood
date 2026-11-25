# Deploying FloodResQ

One container serves both the API and the built React app.

## Render (free tier), step by step

1. In Render: **New + → Blueprint**, then select the `bigmike12/flood` repository.
   Render reads `render.yaml` and creates a Docker web service named `floodresq` on the free plan.
2. When prompted, enter `FLOOD_ADMIN_PASSWORD` and `FLOOD_PLANNER_PASSWORD`.
   Do not use the README demo passwords on a public URL.
   `FLOOD_SECRET` is generated automatically.
3. Wait for the first build (several minutes). The health check is `/api/health`.
4. Open the URL and sign in as `planner` with the password you set.

Redeploy by pushing to `main`; Render rebuilds automatically.

### Free-tier limits (plan for these before Friday)

- **Cold start about 2 minutes.** The service sleeps after about 15 minutes without traffic.
  Open the URL and sign in at least 5 minutes before the presentation.
- **No persistent disk.** The database resets on every redeploy or restart. Accounts are recreated
  from the environment variables, but saved scenarios are lost. Do not rely on saved scenarios.
- **About 0.1 CPU and 512 MB RAM.** Measured in a container with the same limits: memory peaked
  at about 180 MB, a single live simulation takes about 30 s, and a 6-seed comparison in the report setup
  took 5.5 minutes (the live setup is heavier and was not timed). **Do not run comparisons live on the free tier.** The report's 30-seed results
  are served precomputed (`/api/report/results`), and the "Show 30-seed results" button uses them.

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
| `FLOOD_DB` | Set by image | SQLite path, `/data/flood_sim.db` in the container. Mount a volume on `/data` to keep data across restarts. |
| `PORT` | Set by host | Port to listen on (defaults to 8000). Render and similar hosts inject it. |

## Verified before writing this file

- `docker build` completes; the image is about 1.1 GB.
- `tests/e2e_api.py` passes 46/46 against the container.
- Under the free-tier limits (`--memory=512m --cpus=0.1`): the container starts, login works,
  and `/api/report/results` responds in under half a second.
- Backend `pytest`: 8/8 passing.

## Known limitations (acceptable for a demo, not for production)

- CORS allows any origin (`allow_origins=["*"]`).
- `POST /api/scenarios/{id}/run` does not check that the caller owns the scenario.
- Rate limiting is in-memory and resets on restart.
- SQLite supports a single writer; keep one instance.
