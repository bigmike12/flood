# Defence brief: what the evidence supports

Read before the defence. Numbers are from the regenerated 30-seed run in `backend/experiments/results/`
and from the app's Report setup, which reproduces that run exactly.

## 1. The corrected headline numbers

These are the only numbers the code supports. The earlier figures (55.6% vs 45.9%, averting ~12 casualties)
came from a **10-seed** run (seeds 0–9) that was labelled as 30 seeds. They are superseded.

| Strategy (30 seeds, mean) | Coverage | Casualties | Averted vs random | Mean response time |
|---|---|---|---|---|
| Random | 44.1% | 85.2 | — | 47.5 min |
| Nearest-depot | 50.5% | 78.1 | 7.1 | 47.5 min |
| Population-proportional | 50.3% | 77.1 | 8.1 | 48.2 min |
| AI-optimised | 51.0% | 76.9 | 8.3 | 46.7 min |

**What you can claim:**
- Coordinated dispatch beats random dispatch: about +7 points of demand coverage, and about 8 fewer casualties per scenario.
- The Hungarian-optimised allocation is the best of the four on coverage and casualties, and slightly the fastest on mean response time (about 0.8 min).
- The margin over the greedy heuristics (nearest-depot, population-proportional) is small, about one casualty. Say this if asked.

**What you cannot claim:**
- "58% faster response", "94% coverage", "89% utilisation". Nothing in the code produces these.
- Any "17.6 min" or "41.7 min" response-time figures.

## 2. Slides and report: decision needed

- **Final-defence slides 9–10** still show the unsupported claims (58%, 94%, 89%, 17.6/41.7/28.4 min). These need replacing with the table above. I have not edited the deck.
- **Report Chapter 4** states 55.6% vs 45.9% and "about twelve casualties averted". These need the same correction. I have not edited the report.
- **Viva sheet Q16** repeats the 55.6% / 45.9% / ~12 figures. Same correction needed.

## 3. The app's comparison now reproduces the report

The UI has a **Setup** selector:
- **Report setup (default):** the same 36×36 grid, default terrain, and no risk surface as `run_experiments.py`. The 30-seed comparison matches the table above exactly. The region selector and risk heat-map are disabled in this mode because the setup doesn't use them.
- **Live map:** the selected region's terrain, a 40×40 grid, and the ML risk surface. This is for the interactive map, where results differ from the report. The 6-seed comparison in this mode is a different result set.

Use the Report setup for any numbers you quote. Use the Live map to show the flood, roads, and risk heat-map.

## 4. Demo script

1. Sign in, Report setup. Press **Run 30-seed comparison**. Point to the table. (The comparison takes about a minute on the server.)
2. Switch to Live map, pick Lokoja. Toggle the risk heat-map (ROC-AUC ≈ 0.84 on the held-out split).
3. Run Random, then AI-optimised, at the same seed. Single runs vary, so say the comparison above is the evidence and the animation is illustration.
4. Get the AI recommendation. Note: at 2 seeds it could name random as best, a known text issue; the 30-seed comparison is stable.

## 5. Viva answers to update

- **Q16 (results):** use the table in section 1. Mention response time is about 0.8 min faster, not 58%.
- **Q14 (limitations):** the live map and the report setup differ on purpose. Be ready to explain why.
- **Q8 (ROC-AUC 0.84):** verified. Live endpoint returns 0.838; accuracy 0.75 is in the report.

## 6. Checks

- Backend: 8/8 pytest tests pass (includes a test that the app's Report setup equals the harness).
- API end-to-end: 44/44 checks pass (`backend/tests/e2e_api.py`).
- Report setup over the API at 30 seeds matches `summary.json` exactly.
- Browser click-through: **not done** (Chrome extension not connected). Do a five-minute manual run before the defence.
- Seeded accounts use README demo passwords. Change them before any public deployment (`DEPLOY.md`).
