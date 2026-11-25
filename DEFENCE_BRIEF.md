# Defence brief: what the evidence supports

Prepared from a full check of the code, tests, and documents. Read this before the defence.

## 1. Fix before the defence: slides 9 and 10 (Project II deck)

The final-defence deck states results that the code does not produce.

| Slide claim | What the code measures |
|---|---|
| "17.6 min AI mean response time, ↓58% vs random (41.7 min), ↓38% vs nearest (28.4 min)" | Chapter 4 (30 seeds): random **46.55 min**, AI **46.85 min**, nearest **47.7 min**. AI is not faster. |
| "Coverage reached 94% and utilisation 89%" | Chapter 4: AI coverage **55.6%**, utilisation **51.3%**. Live default config: about 44%. |

The 58% figure traces back to the early proposal target ("Expected cut in mean response time 58%"), which was carried into the final deck as a result. The proposal slide labelled it as a target. The final deck does not.

**What the evidence supports** (Chapter 4 report, 30 seeds, the numbers in `experiments/results/summary.json`):

- Coverage: AI **55.6%** vs random **45.9%** (about +10 points).
- Casualties: AI **71.7** vs random **83.6**, so about **12 averted** per scenario.
- Nearest-depot (73.1 casualties) and population-proportional (73.2) are close behind AI. AI's edge over the greedy heuristic is small.
- Response time: no meaningful difference between strategies.

**Recommended slide wording:** "Coordinated, optimised dispatch raised demand coverage from 45.9% to 55.6% and averted about 12 casualties per scenario (30 seeds). Response time was not improved in this model."

I have not edited the deck. Changing the claims is your call, and I can update the slides if you tell me which wording to use.

## 2. The live demo does not reproduce Chapter 4

The Chapter 4 figures come from `run_experiments.py` (grid 36, no region terrain, no ML risk surface). The UI and API use grid 40, the Lokoja terrain, and the risk surface. I checked both at 10 seeds:

| Configuration | Random (cov / casualties) | AI-optimised (cov / casualties) |
|---|---|---|
| Chapter 4 (experiment script) | 45.9% / 83.6 | 55.6% / 71.7 |
| Live UI / API defaults | 37.8% / 110.5 | 44.3% / 102.4 |

AI still beats random on average in the live config, but by less. At the UI's default seed (42), **random beats AI** on both coverage (35.8% vs 32.4%) and casualties (112 vs 118). Do not run that seed as the "AI wins" demo.

**Options (pick one):**
- **A. Present the mismatch honestly.** Say the live demo uses a more realistic terrain and risk surface, that the Chapter 4 numbers use a simpler configuration, and that the direction holds but magnitudes differ.
- **B. Add a "Chapter 4 configuration" option** to the UI so the live numbers match the report. This is a small code change; I can make it if you want.
- **C. Choose a demo seed** where AI wins. This is cherry-picking unless you disclose it, so I would not recommend it.

## 3. Demo script adjustments

- Use **"Run 6-seed comparison"** as the headline. In the live config it shows AI ahead on coverage (44.3% vs 37.1%) and casualties (104 vs 112) at 6 seeds. It also averages over seeds, which an examiner will respect more than one run.
- At **30 seeds** in the live config, AI still leads on coverage (43.9% vs 39.3%) but **nearest-depot and population-proportional have slightly fewer casualties** (101.5 and 101.6 vs 102.3). Say this if asked; it is consistent with the report's "edged out" wording.
- If you do a single run, avoid seed 42 for the "AI wins" moment.
- **Known bug:** when the recommendation picks *random* as best, the text still reads "Versus uncoordinated (random) dispatch…". This happened in my test at 2 seeds. Use 6 seeds for the live demo.

## 4. Viva answers to update

- **Q16 (results):** add that response time did not improve, and that the advantage over the greedy heuristic is small. The current answer says the AI "edged out" nearest-depot, which is accurate; it does not mention that response time was flat.
- **Q14 / limitations:** the live demo configuration differs from the experiment configuration. Be ready to explain this.
- **Q8 (ROC-AUC 0.84):** verified. The live endpoint returns 0.838 and the Random Forest is in `ml_risk.py`. The Chapter 4 report also gives accuracy 0.75.

## 5. Checks I could not complete

- **Browser click-through: not done.** The Chrome extension was not connected. Please do a 5-minute manual run of the demo script in the browser before the defence. The API suite (42/42, in `backend/tests/e2e_api.py`) covers the same endpoints.
- **Seeded accounts.** The default passwords are documented in the README. Change them before any public deployment (see `DEPLOY.md`).

## 6. What is verified

- Backend: 6/6 `pytest` tests pass (Python 3.11 venv at `backend/.venv311`).
- API end-to-end: 42/42 checks pass against both the dev server and the Docker container.
- Container: builds, runs, serves the UI, and keeps saved scenarios across restarts.
- Frontend: TypeScript and Vite build clean; the bundle is served over HTTP.
