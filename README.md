# Senior Safety Web Agent

Hackathon app with two tabs. **My subscriptions** is first: add by hand or screenshot, then optional GymPlus cancel recipe. **Scan a site** rates **Payment Safety** (is this snapshot a risky place to type a card) — not an accessibility-for-seniors score.

This file is the honest inventory: what we built, what we did not, licenses, demo secrets that are *supposed* to be public, and what is still broken.

## Demo login (judges and teammates)

This is a **throwaway account for our app only**. It is not a real email, bank, Google, Groq, or Steel login.

| | |
| --- | --- |
| **Username** | `judge@demo.local` |
| **Password** | `SeniorSafety2026` |

Same values live in `backend/.env.example` as `DEMO_USER` / `DEMO_PASSWORD`. Anyone who can open this repo can sign in to a local copy. That is intentional for the hackathon.

**API keys are not in this README and must not be committed.** Put `STEEL_API_KEY`, `SAFE_BROWSING_API_KEY`, `OPENAI_API_KEY` (Groq `gsk_…` is fine for screenshot vision), and optional `ANTHROPIC_API_KEY` (Claude, used first if set) only in `backend/.env`.

After you sign in, a session cookie (`sameSite=lax`) keeps you signed in until you sign out or the cookie expires (`SESSION_MAX_AGE`). The secret that signs the cookie is `SESSION_SECRET` in `.env`. The example value is a **dev default**, not production-grade.

## How to run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # local Playwright bits; Steel still hosts cloud Chrome
cp .env.example .env                    # then fill real API keys
python -m classifier.train              # trains on Yamana TSV only

cd ../frontend
npm install
```

Terminal 1:

```bash
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend && npm run dev
```

Open **http://localhost:5173** (Vite proxies `/auth`, `/scan`, `/demo`, `/health` to port 8000). Signing in against the API directly at `:8000` will not set the cookie the UI expects unless you use the proxied origin.

## What a scan does

1. You must be signed in.
2. `POST /scan` with `{ "url", "skip_agent": true, "include_a11y": false }` by default.
3. **Without** accessibility scan: Steel `/v1/scrape` pulls HTML/text.
4. **With** “Include accessibility scan”: a Steel Chrome tab + Playwright CDP loads the page, injects vendored **axe-core**, maps a few rules into senior language, and reuses that HTML/text. If that fails, we fall back to `/v1/scrape`.
5. BeautifulSoup heuristics + a scikit-learn model (Yamana labels) produce **senior flags** and wording categories.
6. Google Safe Browsing is queried if a key is set.
7. **Senior Safety Score** is 0–100, **higher = safer** (decision S1). Bands: 80+ easier for seniors, 50–79 use with care, below 50 easy to get stuck or miss fees.
8. The old **Browser Use** cancel agent still exists in code. The UI skips it by default. Do not turn it on unless you know it will spend LLM + Steel time.

`GET /scan/{id}` returns the job, live `trace[]`, and `report` when complete.

Optional **Run Steel login demo** (`POST /demo/login`) injects a fake HTML login page *inside Steel* and types the demo credentials. Steel cloud Chrome **cannot see `localhost`**, so this is not “log into our Vite app from the cloud.”

## UI modes

**Standard** vs **Accessibility-Friendly** only restyles *our* React screens (`html[data-a11y=on]`, remembered in `localStorage`). It does not restyle the site you scanned.

## Locked product decisions

| ID | Choice |
| --- | --- |
| Runtime | FastAPI + this Vite/React app. Steel hosts Chrome. Playwright `connect_over_cdp`. **No LLM click-agent for navigation.** |
| Login | Our app login. Demo account **in this README**. |
| A11y toggle | Our UI only. |
| Phase 2 data | **Y1** Yamana TSV (Apache-2.0). **M2** Mathur CSVs not in the repo. |
| Parser | **P1** BeautifulSoup. |
| Findings UI | Payment Safety + wording categories (Yamana / Mathur taxonomy) |
| Scan a11y rating | Removed from the product UI |
| Payment Safety | Safe Browsing + payment-related dark-pattern categories + cancel/fee heuristics |

## Copyright and licenses (what we ship vs cite)

We are not lawyers. This is what we actually put in the repo and what we refused to copy.

### Shipped in this repository

| Artifact | License | Where | What we did |
| --- | --- | --- | --- |
| Yamana `ec-darkpattern` TSV | Apache-2.0 | `backend/classifier/data/` + `NOTICE.txt` | Train the wording model. Keep their notice. Paper: [arXiv:2211.06543](https://arxiv.org/abs/2211.06543). |
| axe-core 4.10.3 (`axe.min.js`) | [MPL-2.0](https://www.mozilla.org/en-US/MPL/2.0/) | `backend/detect/vendor/` | Used **as a library**, injected into the Steel page. **Not modified.** License text: `LICENSE-axe-core.txt`. MPL requires that if you distribute this file, you keep the license and notice. |
| Our application code | Your/hackathon project code | `backend/`, `frontend/` | Original wiring, heuristics, score, UI. |

### Cited only — do **not** copy their code, crawlers, or dumps into this repo

| Source | Why we do not vendor it |
| --- | --- |
| Mathur et al., *Dark Patterns at Scale* [arXiv:1907.07032](https://arxiv.org/abs/1907.07032) | The **paper** is citable. The [GitHub repo](https://github.com/aruneshmathur/dark-patterns) is **GPLv3**. We do **not** vendor that crawler or their CSVs. Yamana already derived similar positive strings and published them under Apache-2.0; we cite Mathur as the academic source of the pattern types. |
| WebAIM Million / WAVE exports | Cite WebAIM if you talk about prevalence. **Do not** redistribute WAVE dumps; see [WAVE terms](https://wave.webaim.org/terms). |
| AccessGuru / DPDGPT (CC BY 4.0) | Allowed with credit. We **did not pull them** (G1) to keep the pipeline small. |

### Third-party services (not redistributed)

Steel, Google Safe Browsing, and Groq/OpenAI are used over the network under *their* terms. We do not bundle their models or browsers. Keys stay in `.env`.

### Original sites you scan

Scraping someone else’s page for a demo is not a license to republish their HTML, logos, or articles. The report keeps a **short text preview**, not a full mirror. Do not dump live page HTML into git.

## Payment Safety (transparent, not scientific)

Three bands: **No obvious payment traps**, **Be careful before you pay**, **Do not enter a card here**.

Risk goes up for Safe Browsing malware, and for Yamana/Mathur-style categories that affect checkout (Sneaking, Forced Action, Obstruction, Urgency, Scarcity, Misdirection), plus cancel-trap / hidden-fee heuristics.

**Not** WCAG. **Not** “safe to pay.” Screenshot add uses Groq vision (Claude if `ANTHROPIC_API_KEY` is set) and never auto-saves.

We still **do not vendor Mathur’s GPLv3 CSVs**. Payment wording uses Yamana Apache-2.0, which uses the same category names as Mathur 2019.

## Judge test templates

Offline (no Steel / Groq / live sites), from `backend`:

```bash
.venv/bin/python test_offline.py
```

**Do not** use a real paid Netflix/Spotify password on a machine you do not trust. Semi-assisted cancel opens **Steel cloud Chrome**, which is not your laptop. CAPTCHA/2FA should **pause**, not get bypassed.

### T1 — Sign in and tab order
1. Open the app. Sign in with the demo account.
2. Expect **My subscriptions** first, then **Scan a site**.
3. Toggle Accessibility-Friendly Mode: only *our* UI changes.

### T2 — Manual add
1. Add `GymPlus` + `https://example.com`.
2. Add `Netflix` + `https://www.netflix.com` (or another public site).
3. Expect both rows. Guide me on both. Semi-assisted cancel on both.

### T3 — Guide me (no auto-click)
1. On Netflix (or any live URL), click **Guide me**.
2. Expect a **checklist only** — no Steel, no scrape, no “could not load public snapshot.” Netflix is not opened from our servers.
3. Tick boxes. We must not claim the subscription is cancelled.

### T4 — GymPlus semi-assisted (fake cancel, in-app, no Steel)
1. On GymPlus, **Semi-assisted cancel** → confirm.
2. Expect the fake GymPlus page **in this app**, not a Steel viewer.
3. Click **Cancel membership** on the demo, then **Yes, cancel now** (or **Yes, click the last Cancel button**).
4. Expect **Membership cancelled. You will not be billed again.**
5. Not Browser Use. Not a real gym.

### T5 — Generic live site pause (uses Steel minutes)
1. On Netflix (or `https://example.org`), **Semi-assisted cancel** → confirm.
2. Expect a Steel tab to open the **live URL**.
3. Expect a **pause**: login wall, bot check, CAPTCHA, missing Cancel, or (rare) a Cancel control waiting for confirm.
4. Expect copy like **Stuck at [step] — needs your input** plus **I've done that step, continue** and a link to open the page on your own device.
5. We must **not** solve a CAPTCHA or type 2FA.

### T6 — Scan / Payment Safety (uses Steel scrape)
1. **Scan a site** → `https://example.com`.
2. Expect **Payment Safety** (not a 0–100 senior/accessibility score).
3. Safe Browsing may be unavailable; that must not look like Steel failed if scrape is ok.

### T7 — Screenshot prefill (Groq)
1. Paste or upload a fake bill image (not a real bank statement if you can avoid it).
2. **Read screenshot into the form**.
3. Expect fields to fill or a clear error. **Add subscription** is still required to save.
4. We must not invent a Netflix cancel URL that was not in the picture.

### T8 — Session gone
1. Restart the API while a scan is polling.
2. Expect a clear “scan is gone / run again” — not an infinite 404 loop.

### T9 — What must never happen
- Browser Use choosing clicks on a live bill.
- Keys printed in the report.
- Claiming we cancelled Netflix without a confirm + a real in-session click you approved.

## Honest gaps and known bugs

- **Google Safe Browsing** may fail (HTTP 400) if the key is not a Google Cloud Browser API key (usually starts with `AIza`). The scan still finishes; the badge may be `error`. Error text is **sanitized** so the key is not echoed in the UI (httpx used to put `?key=…` in `HTTPStatusError`). If you ever saw a key in a scan error, **rotate it**.
- The wording model includes a **Not Dark Pattern** class. We drop that label from the report so a clean page is not listed as a “pattern.”
- **Steel minutes** are real money/quota. Every scrape, login demo, and axe scan opens cloud Chrome. Cloud Chrome **cannot load your localhost UI**.
- **`backend/agent/cancel_flow.py`** still depends on `browser-use`. Left in the tree; default path does not call it. That is leftover, not the Phase 1 navigation design.
- Classifier quality is only as good as Yamana’s labels plus our regex/DOM heuristics. False positives and missed patterns will happen.
- axe is mapped for a **small set** of rule ids (contrast, alt text, labels, button/link names, title, lang, target size). Other axe violations still appear with a generic “page barrier” sentence.
- Jobs live **in memory**. Restarting uvicorn wipes scans. Not multi-user safe beyond a shared demo password.
- CORS is localhost:5173 only.
- Accessibility-Friendly mode does not claim WCAG 2.x conformance for our own UI.
- We did not run a lawyer review. License table above is our working stance.

## API (current)

| Method | Path | Auth | Body / notes |
| --- | --- | --- | --- |
| GET | `/health` | no | `{ "status": "ok" }` |
| POST | `/auth/login` | no | `{ "username", "password" }` → session cookie |
| POST | `/auth/logout` | cookie | |
| GET | `/auth/me` | cookie | |
| POST | `/demo/login` | cookie | Steel + Playwright demo; uses Steel quota |
| POST | `/scan` | cookie | `{ "url", "skip_agent": true }` |
| GET | `/scan/{scan_id}` | cookie | Job + `report.payment_safety` |
| GET/POST | `/subscriptions/` | cookie | Manual list |
| POST | `/subscriptions/extract` | cookie | Screenshot → fields (not saved) |
| POST | `/subscriptions/{id}/guide` | cookie | Static checklist only; does not visit the merchant |
| POST | `/subscriptions/{id}/cancel` | cookie | Semi-assisted Playwright; `{ confirmed: true }` |
| POST | `/subscriptions/jobs/{id}/confirm` | cookie | Continue or last-click confirm |

## Repo map (phases 1–4)

| Area | Files |
| --- | --- |
| Auth | `backend/auth.py` |
| Scan orchestration | `backend/main.py` |
| Steel + Playwright | `backend/nav/steel_playwright.py`, `backend/nav/login_demo.py` |
| Scrape / leftover agent | `backend/agent/scrape.py`, `backend/agent/cancel_flow.py` |
| Heuristics + senior copy | `backend/detect/heuristics.py`, `backend/detect/senior_copy.py` |
| axe | `backend/detect/a11y.py`, `backend/detect/vendor/` |
| Score | `backend/score/payment.py` |
| Subscriptions | `backend/subscriptions/` + `frontend/src/Subscriptions.jsx` |
| Recipes / blockers | `backend/nav/recipe_player.py`, `backend/nav/blockers.py`, `backend/nav/gymplus_page.py` |
| Classifier | `backend/classifier/` (train, predict, Yamana TSV + NOTICE) |
| Safe Browsing | `backend/safety/check.py` |
| UI | `frontend/src/App.jsx`, `a11y.jsx`, `App.css` |

Phase 5 (same React app, score + flags on the report) is in that UI. There is no second frontend.
