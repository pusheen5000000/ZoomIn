# ZoomIn

Hackathon app for **older adults and the people helping them**: list subscriptions, get a plain-language cancel checklist, try a **fake** GymPlus cancel in our UI, and **scan a public page** for payment-related dark patterns.

We use **Steel.dev cloud Chrome** to scrape and (on live URLs) to drive a real browser with Playwright. We do **not** use an LLM to click. We do **not** claim we cancelled Netflix.

---

## Contents

1. [What we built](#what-we-built)
2. [Judge demo (start here)](#judge-demo-start-here)
3. [How to run](#how-to-run)
4. [How it works](#how-it-works)
5. [Tests](#tests)
6. [Honest limits](#honest-limits)
7. [Licenses](#licenses)
8. [References](#references)
9. [API](#api)
10. [Repo map](#repo-map)

---



## What we built

Two tabs. **My subscriptions** is first.


| Feature                | What it does                                                                                  | Steel?                           |
| ---------------------- | --------------------------------------------------------------------------------------------- | -------------------------------- |
| Sign in                | Throwaway app account (below). Cookie session.                                                | No                               |
| Add subscription       | Type name + URL, or upload a bill screenshot                                                  | No (Groq/Claude reads the image) |
| **Guide me**           | Checklist on **your** device. We do not open Netflix.                                         | No                               |
| **GymPlus cancel**     | Fake membership page **in this app**. Confirm last click.                                     | No                               |
| **Live cancel**        | Opens the real URL in Steel Chrome, tries Account/Cancel, **pauses** on captcha / login / 2FA | Yes                              |
| **Scan a site**        | Steel scrape → wording classifier + DOM heuristics + Safe Browsing → **Payment Safety**       | Yes                              |
| Accessibility-Friendly | Larger type / our screens only. Does not restyle Netflix.                                     | No                               |
| Steel login demo       | Injects a fake login form *inside* cloud Chrome and types the demo creds                      | Yes                              |


**Payment Safety** is three bands: no obvious traps on this snapshot / be careful / do not enter a card. It is **not** WCAG, **not** a 0–100 “senior score,” and **not** a bank guarantee.

**Detection** is a scikit-learn classifier trained on the **Yamana** TSV, plus BeautifulSoup/regex heuristics. Mathur 2019 is the **taxonomy we cite**; we did not copy their GitHub dump. Groq is **not** the dark-pattern judge.

---



## Judge demo (start here)



### Login (our app only)

This is **not** Netflix, Google, Groq, or Steel.


|          |                                                                                   |
| -------- | --------------------------------------------------------------------------------- |
| URL      | **[http://localhost:5173](http://localhost:5173)** (use this origin, not `:8000`) |
| Username | `judge@demo.local`                                                                |
| Password | `SeniorSafety2026`                                                                |


Same values: `backend/.env.example` (`DEMO_USER` / `DEMO_PASSWORD`). Anyone with the repo can sign in locally. That is intentional.

**API keys stay in gitignored** `backend/.env`**.** Never paste them into the UI or this file.

### Demo examples 

**GymPlus (Fake website for testing)**

1. Sign in. Confirm **My subscriptions** is the first tab. Optional: toggle Accessibility-Friendly — only *our* chrome changes.
2. Add **GymPlus** + `https://example.com`.
3. Click **Cancellation guide** to view the checklist only.
4. Click **Assisted help to cancel** on GymPlus → confirm → Click **Yes, cancel**. Confirm cancellation by clicking **Cancel membership**. 

**Netflix (For testing)**

1. Add **Netflix** + `https://www.netflix.com`.
2. Click **Cancellation guide** — gives detailed cancellation step-by-step guide 
6. Optional: Netflix **Assisted help to cancel**. Steel opens the live site, and if the cancellation needs human interface (login/verification), Steel will pause at that step. The website shows guidance for what to do next. 


**Scan a site** 
1. Enter `https://example.com`. Expect **Payment Safety** (Steel scrape). Safe Browsing may show `error`; that is not a Steel failure if scrape is ok.


### What must never happen in a demo

- Browser Use picking clicks on a live bill
- API keys in the report
- “We cancelled Netflix” without your confirm **and** a real last click you approved (we do not complete that on Netflix)

---



## How to run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # driver only; Chrome still runs on Steel
cp .env.example .env                    # fill STEEL_API_KEY, etc.
python -m classifier.train              # Yamana TSV only
cd ../frontend && npm install
```

`.env` (not committed): `STEEL_API_KEY`, `SAFE_BROWSING_API_KEY`, `OPENAI_API_KEY` (Groq `gsk_…` is fine), optional `ANTHROPIC_API_KEY`, `SESSION_SECRET` (dev default is not production-grade).

**Terminal 1 — API**

```bash
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000
```

**Terminal 2 — UI**

```bash
cd frontend && npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)**. Vite proxies `/auth`, `/scan`, `/demo`, `/health`, `/subscriptions` to port 8000. Logging in on `:8000` directly will not set the cookie the UI expects.

Jobs live **in memory**. Restarting uvicorn wipes scans and subscription rows.

---



## How it works



### Scan a site

1. Sign in → `POST /scan` (`skip_agent: true` by default).
2. Steel `/v1/scrape` returns HTML/text. (A session is also created so a viewer link can exist; scrape is not bound to `sessionId` because that 404’d.)
3. Optional axe path: Steel tab + Playwright CDP, inject vendored axe-core, then fall back to scrape if that fails. **Not** shown as a senior a11y score in the UI.
4. Chunk text → **TF-IDF + logistic regression** (`backend/classifier/`). Drop the “Not Dark Pattern” label from the report.
5. BeautifulSoup heuristics: urgency copy, call-to-cancel, confirmshaming, pre-checked boxes, tiny text, hidden cancel.
6. Google Safe Browsing if a key is set.
7. **Payment Safety** band + reasons. Poll `GET /scan/{id}`.

**Steel login demo** (`POST /demo/login`): fake HTML inside cloud Chrome. Steel **cannot see localhost**, so this is not “log into our Vite app from the cloud.”

### Subscriptions

- **Guide me** — static steps (Netflix gets a canned Account → Membership path). No Steel.
- **GymPlus** (`example.com` or name GymPlus) — in-app fake page. Confirm last click. No Steel.
- **Any other http URL** — Steel + Playwright: `goto`, try Account/Billing/Cancel selectors, **pause** on captcha / 2FA / bot / payment fields. We name the stall; we do not bypass. Last Cancel still needs confirm.



### Locked choices


|             |                                                      |
| ----------- | ---------------------------------------------------- |
| Runtime     | FastAPI + Vite/React                                 |
| Browser     | **Steel Browser** (cloud Chrome), not Steel Computer |
| Clicks      | Playwright recipes. **No LLM click-agent**           |
| Data        | Yamana TSV in repo. Mathur paper cite-only           |
| Parser      | BeautifulSoup                                        |
| Score in UI | Payment Safety, not a senior 0–100                   |


---



## Tests

```bash
cd backend
.venv/bin/python test_offline.py   # no Steel / Groq / network
.venv/bin/python test_live.py      # needs API up; uses Steel + Groq minutes
```

Live script logs in as the demo user, adds GymPlus + Netflix, checks Guide me does not visit, extracts a fake PNG, scans example.com, completes GymPlus cancel, and expects Netflix cancel to **pause**.

Do not use a real paid-account password in Steel.

---



## Honest limits

- Safe Browsing often **HTTP 400** if the key is not a Google `AIza…` Browser API key. Scan still finishes. Errors are sanitized (no `?key=` in the UI). Rotate a key if it ever leaked in a report.
- Classifier = Yamana strings + our regex/DOM. Marketing “SALE” can look like Urgency. We have a train/test split on **their TSV**, not a senior clinical study.
- Steel minutes cost money. Viewer lasts ~2 minutes. Cloud Chrome ≠ the user’s laptop.
- `backend/agent/cancel_flow.py` still imports **browser-use**. Default path does not call it.
- axe maps a **small** set of rules; other hits get a generic sentence. Accessibility-Friendly mode is **not** a WCAG claim for our UI.
- CORS: localhost:5173 only. Not multi-user beyond the shared demo password.

---

## Licenses

Hackathon code in this repo is ours. Third-party pieces we actually ship:

- **Yamana** dark-pattern TSV — Apache-2.0 (`backend/classifier/data/` + their `NOTICE.txt`)
- **axe-core** 4.10.3 — MPL-2.0, unmodified (`backend/detect/vendor/`)

Mathur 2019 is cited for category names only; we do not include their GPLv3 crawler or CSVs. Steel, Groq, Claude, and Safe Browsing are remote APIs (keys in `.env`, never in git).

---

## References



### How each source is used


| Source                          | In the product?                       | Role                                                            |
| ------------------------------- | ------------------------------------- | --------------------------------------------------------------- |
| Yamana Lab *ec-darkpattern* TSV | **Yes** (`yamana-ec-darkpattern.tsv`) | Train TF-IDF + logistic regression                              |
| Mathur et al. 2019              | **Cite only**                         | Category names. No GPLv3 files                                  |
| Yada et al. 2022                | Cite                                  | Paper for the TSV (their RoBERTa baseline is **not** our model) |
| Cialdini, *Influence*           | Cite                                  | Explanations in `backend/psych/mapping.json`                    |
| axe-core 4.10.3                 | **Yes**                               | Optional rules in Steel Chrome                                  |
| Steel.dev Browser               | **API**                               | Scrape + session + CDP                                          |
| Playwright                      | **Yes**                               | Drive Steel; not an LLM clicker                                 |
| scikit-learn / joblib           | **Yes**                               | `dark_patterns.joblib`                                          |
| BeautifulSoup4                  | **Yes**                               | DOM heuristics                                                  |
| Groq                            | **API**                               | Screenshot → form fields only                                   |
| Anthropic Claude                | **API** (optional)                    | Same extract if key set                                         |
| Google Safe Browsing            | **API**                               | URL malware check                                               |
| FastAPI, Uvicorn, React, Vite   | **Yes**                               | App                                                             |
| Browser Use                     | Tree, **off**                         | Leftover                                                        |
| WAVE / AccessGuru               | **Not used**                          | So we do not claim we shipped them                              |




### Dataset and papers

1. **Yamana Laboratory.** *EC Dark Pattern Dataset*. [yamanalab/ec-darkpattern](https://github.com/yamanalab/ec-darkpattern) (Apache-2.0). Local: `backend/classifier/data/`. Upstream: `https://raw.githubusercontent.com/yamanalab/ec-darkpattern/master/dataset/dataset.tsv`.
2. **Yada, Y., Feng, J., Matsumoto, T., Fukushima, N., Kido, F., and Yamana, H.** (2022). *Dark patterns in e-commerce: a dataset and its baseline evaluations*. IEEE BigData 2022. [arXiv:2211.06543](https://arxiv.org/abs/2211.06543).
3. **Mathur, A., Acar, G., Friedman, M. J., Lucherini, E., Mayer, J., Chetty, M., and Narayanan, A.** (2019). *Dark Patterns at Scale: Findings from a Crawl of 11K Shopping Websites*. PACM HCI (CSCW). [arXiv:1907.07032](https://arxiv.org/abs/1907.07032).
4. **Cialdini, R. B.** *Influence: The Psychology of Persuasion*. Harper Business.
5. **Brignull, H.** *Deceptive patterns* (formerly darkpatterns.org). Term origin; we do not ship that corpus.



### Software and APIs

1. **Deque.** axe-core v4.10.3. [github.com/dequelabs/axe-core](https://github.com/dequelabs/axe-core) (MPL-2.0).
2. **Pedregosa, F., et al.** (2011). *Scikit-learn: Machine Learning in Python*. JMLR 12.
3. **Beautiful Soup** — HTML parser for heuristics.
4. **Steel.dev** — [docs.steel.dev](https://docs.steel.dev). **Browser**, not Computer.
5. **Playwright** — [playwright.dev](https://playwright.dev). CDP into Steel.
6. **Google Safe Browsing** — [developers.google.com/safe-browsing](https://developers.google.com/safe-browsing).
7. **Groq** — [groq.com](https://groq.com) (`OPENAI_BASE_URL=https://api.groq.com/openai/v1`).
8. **Anthropic** — [docs.anthropic.com](https://docs.anthropic.com).
9. **FastAPI**, Uvicorn, Pydantic, httpx, python-dotenv.
10. **React**, **Vite**.
11. **Browser Use** — leftover. [github.com/browser-use/browser-use](https://github.com/browser-use/browser-use).

---



## API

Vite proxies these from `:5173`. Cookie = signed-in demo user.


| Method   | Path                               | Auth   | Notes                                  |
| -------- | ---------------------------------- | ------ | -------------------------------------- |
| GET      | `/health`                          | no     | `{ "status": "ok" }`                   |
| POST     | `/auth/login`                      | no     | `{ "username", "password" }`           |
| POST     | `/auth/logout`                     | cookie |                                        |
| GET      | `/auth/me`                         | cookie |                                        |
| POST     | `/demo/login`                      | cookie | Steel + Playwright fake login          |
| POST     | `/scan`                            | cookie | `{ "url", "skip_agent": true }`        |
| GET      | `/scan/{id}`                       | cookie | Job + `report.payment_safety`          |
| GET/POST | `/subscriptions/`                  | cookie | List / add                             |
| POST     | `/subscriptions/extract`           | cookie | Screenshot → fields (not saved)        |
| POST     | `/subscriptions/{id}/guide`        | cookie | Checklist; does not visit the merchant |
| POST     | `/subscriptions/{id}/cancel`       | cookie | `{ "confirmed": true }`                |
| POST     | `/subscriptions/jobs/{id}/confirm` | cookie | Continue or last click                 |


---



## Repo map


| Area                   | Files                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------- |
| Auth                   | `backend/auth.py`                                                                        |
| Scan                   | `backend/main.py`                                                                        |
| Steel session / scrape | `backend/agent/steel_session.py`, `backend/agent/scrape.py`                              |
| Playwright on Steel    | `backend/nav/steel_playwright.py`, `backend/nav/login_demo.py`                           |
| Cancel recipes         | `backend/nav/recipe_player.py`, `backend/nav/blockers.py`, `backend/nav/gymplus_page.py` |
| Leftover agent         | `backend/agent/cancel_flow.py`                                                           |
| Heuristics             | `backend/detect/heuristics.py`, `backend/detect/senior_copy.py`                          |
| axe                    | `backend/detect/a11y.py`, `backend/detect/vendor/`                                       |
| Payment Safety         | `backend/score/payment.py`                                                               |
| Classifier             | `backend/classifier/` (train, predict, Yamana TSV + NOTICE)                              |
| Safe Browsing          | `backend/safety/check.py`                                                                |
| Subscriptions          | `backend/subscriptions/`, `frontend/src/Subscriptions.jsx`                               |
| UI                     | `frontend/src/App.jsx`, `a11y.jsx`, `App.css`                                            |
