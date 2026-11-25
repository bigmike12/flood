# Defence brief: what the evidence supports

Numbers are from the 30-seed run in `backend/experiments/results/` (mean over seeds 0–29, report setup).
The app serves exactly these numbers from `/api/report/results`.

## 1. Headline numbers

| Strategy (30 seeds, mean) | Coverage | Casualties | Averted vs random | Mean response time |
|---|---|---|---|---|
| Random | 44.1% | 85.2 | — | 47.5 min |
| Nearest-depot | 50.5% | 78.1 | 7.1 | 47.5 min |
| Population-proportional | 50.3% | 77.1 | 8.1 | 48.2 min |
| AI-optimised | 51.0% | 76.9 | 8.3 | 46.7 min |

**What you can claim**
- Coordinated dispatch beats random dispatch: about +7 points of demand coverage and about 8 fewer casualties per scenario.
- AI-optimised is the best of the four on coverage and casualties, and slightly the fastest on mean response time (about 0.8 min).
- The margin over the greedy heuristics is small: about one casualty, and +0.5 points of coverage over nearest-depot.
- The advantage grows with resources (responder units, 30 seeds each): casualties averted 0.3 at 4 units, 5.4 at 10, 8.3 at 20. Coverage gain over random is +3.2, +5.2, +6.9 at the same settings.

**What you cannot claim**
- "58% faster response", "94% coverage", "89% utilisation", "17.6 min" or "41.7 min". None of these comes from the code.
- That the AI advantage is largest under scarce resources. The measured advantage is smallest when resources are scarce.
- That AI raises utilisation. Random dispatch has higher utilisation (55.4% vs 51.3%).

## 2. Slides: updated in the Project II deck

The Final Defence deck (`Defense Slides - Project II (Final Defence).pptx`) has been corrected.
The original is kept at the scratchpad path noted in the session.

- **Slide 3:** "Advantage of good allocation is greatest when resources are scarce" → "Allocation choices directly change how many people are reached in time."
- **Slide 9:** title → "AI Allocation Gives Highest Coverage". Headline → 51.0% AI-optimised demand coverage, vs 44.1% random (+6.9 pts) and 50.5% nearest-depot (+0.5 pts). Averaged over 30 replications.
- **Slide 10:** key finding → "AI averts 8.3 casualties per scenario vs random (76.9 vs 85.2). The gain grows with resources: 0.3 at 4 units, 5.4 at 10, 8.3 at 20."
- **Slide 11:** "Shows AI allocation improves coverage over random dispatch at every scale tested (4–20 units)."

Not yet checked visually (no LibreOffice on this machine). Slide 11's line is longer than before, so check it wraps cleanly.

**Still to correct (not slides):**
- Report Chapter 4 still says 55.6% vs 45.9% and "about twelve casualties averted".
- Viva sheet Q16 repeats those figures.

## 3. Friday demo (free tier)

1. **Warm up 5 minutes early:** open the Render URL and sign in (cold start is about 2 minutes).
2. Report setup (default) → **Show 30-seed results**. This is instant and shows the table.
3. **Get AI recommendation** (also instant in report setup).
4. Switch to **Live map**, pick Lokoja, toggle the risk heat-map (ROC-AUC ≈ 0.84 on the held-out split). Run Random, then AI-optimised, at the same seed. Keep to single runs, and say the 30-seed table is the evidence; the animation illustrates it.
5. **Do not press Run comparison in Live map on the free tier.** It is slow and will look frozen during the talk.
6. Saved scenarios reset on every restart on the free tier, so do not demo them.

## 4. Viva answers to update

- **Q16 (results):** use the table in section 1. Response time differs by about 0.8 min, not 58%.
- **Q14 (limitations):** the live map and report setup differ on purpose.
- **Q8 (ROC-AUC 0.84):** verified (live endpoint 0.838; accuracy 0.75 in the report).

## 5. Checks

- Backend: 8/8 pytest passing. Includes a test that the report setup equals the evaluation harness.
- API end-to-end: 46/46 against the container, including the precomputed results check.
- Container under free-tier limits (512 MB, 0.1 CPU): starts, logs in, and serves precomputed results in 0.4 s.
- Browser click-through: **not done** (Chrome extension not connected). Do a five-minute manual run before Friday.
