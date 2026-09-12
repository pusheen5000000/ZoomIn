# Subscription Impossible

Hackathon web agent: scrape a URL, classify dark-pattern copy, check Google Safe Browsing, then try to cancel a subscription/trial with Browser Use on a Steel cloud browser.

## What landed on `ema-branch`

Scaffolded the full Python + React skeleton so the three of us can work in parallel. Speckit was **not** used (too much process for 24 hours); this tree is the spec.

| Piece | Status |
| --- | --- |
| FastAPI `POST /scan` + poll `GET /scan/{id}` | Wired: scrape → classifier → Safe Browsing → cancel-flow agent |
| Steel session + `/v1/scrape` | Implemented in `backend/agent/scrape.py` (needs `STEEL_API_KEY`) |
| Browser Use on the same Steel CDP session | Implemented in `backend/agent/cancel_flow.py` (needs `OPENAI_API_KEY` + `pip install browser-use`) |
| TF-IDF + LogisticRegression on Mathur et al. | `python -m classifier.train` — model is gitignored; retrain locally |
| Google Safe Browsing wrapper | `backend/safety/check.py` |
| Cialdini psych mapping | `backend/psych/mapping.json` |
| Vite/React one-pager | URL input, live trace, report card |

The app **boots without API keys**. Scrape/safety/agent then report “key not set” instead of crashing. Check **Skip cancel-flow agent** in the UI while iterating.

**Do not run the full Speckit loop for this.** A 24-hour, 3-person split does not have time for constitution → specify → plan → tasks → implement. This README *is* the shared spec.

## Split the work

| Person | Owns | First green check |
| --- | --- | --- |
| A | `backend/agent`, Steel + Browser Use | `python -m agent.scrape` returns page text |
| B | `backend/classifier` + `backend/psych` | `python -m classifier.train` then `predict()` |
| C | `backend/safety` + `frontend` + `POST /scan` wiring | UI polls a scan and shows a report |

Do not start Browser Use until scrape works. Do not block the UI on a finished classifier — mock empty `patterns: []` if the `.joblib` is missing.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill STEEL_API_KEY, SAFE_BROWSING_API_KEY, OPENAI_API_KEY

python -m classifier.train

cd ../frontend
npm install
```

## Run

```bash
# terminal 1
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Open http://localhost:5173. The UI `POST`s `/scan` then polls `GET /scan/{id}` until status is `complete`.

## Testable backend steps (in order)

1. Steel scrape (hardcoded URL, no Browser Use):

   ```bash
   cd backend && python -m agent.scrape
   ```

2. Browser Use cancel-flow on that Steel session:

   ```bash
   python -m agent.cancel_flow https://example.com
   ```

3. Classifier:

   ```bash
   python -m classifier.train
   python -c "from classifier.predict import predict; print(predict('Only 2 left! Offer expires in 00:05:00'))"
   ```

4. Safety:

   ```bash
   python -m safety.check https://example.com
   ```

5. Psych mapping:

   ```bash
   python -m psych.explain
   ```

6. Full scan (skip agent while iterating UI):

   ```bash
   curl -X POST http://127.0.0.1:8000/scan \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://example.com","skip_agent":true}'
   ```

Then `GET /scan/{scan_id}` from the JSON that comes back.

## API

`POST /scan` `{ "url": "https://…", "skip_agent": false }` → `{ "scan_id", "status" }`

`GET /scan/{scan_id}` → job with `trace[]` (live) and `report` (when complete). The report includes safety verdict, classifier categories + Cialdini copy, scrape preview, and agent steps/friction points.

## Layout

```
backend/agent        Steel session + scrape + Browser Use
backend/classifier   train.py, predict(), bundled Mathur sample CSV
backend/safety       Google Safe Browsing v4 wrapper
backend/psych        category → Cialdini principle + one-sentence explanation
backend/main.py      FastAPI orchestration
frontend/             Vite + React single page
```
