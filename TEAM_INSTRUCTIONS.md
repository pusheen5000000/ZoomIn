# Subscription Impossible — AI Instructions

This file is the single source of truth for any AI assistant (Claude, Cursor,
Copilot, ChatGPT, etc.) working on this project — whether you're pairing with
a human teammate or running semi-autonomously. Read this in full before writing
any code. If a human's request conflicts with this file, flag the conflict and
ask rather than silently picking one.

**Project:** A web agent that detects dark patterns (hard-to-cancel
subscriptions, manipulative UX, fake urgency) and flags malicious/unsafe sites.
**Format:** 24-hour hackathon, team of 3, working in parallel.
**Stack:** Python end-to-end (FastAPI backend, React/Vite frontend). No language split.

---

## 1. Non-negotiable rules for any AI working on this repo

1. **Build only the current step.** Each numbered step in Section 5 must
   produce something runnable and testable before you touch the next one.
   Do not scaffold ahead "to save time" — if asked to build step 2, stop
   after step 2 and show it working.
2. **Never invent an interface.** The shapes in Section 4 (`AgentTrace`,
   `ClassifierResult`, `SafetyVerdict`, `ScanReport`) are frozen. If your
   task needs a shape that isn't defined there, propose the addition and
   flag it — don't silently extend or rename fields other lanes depend on.
3. **No secrets in code, ever.** API keys live in `.env` only. Never write a
   key into a script, a commit, a log statement, or a test fixture. Read
   from environment variables (`os.environ` / `pydantic-settings`), and
   fail loudly with a clear message if one is missing — don't fall back to
   a hardcoded default.
4. **Structured output between components, always.** Any function whose
   result crosses a lane boundary (agent → orchestrator, classifier →
   orchestrator, orchestrator → frontend) returns a typed Python object
   (Pydantic model or dataclass), never a raw string the caller has to
   parse. Free-text LLM output gets parsed into structure before it leaves
   the function that produced it.
5. **Fail visibly, not silently.** Wrap external calls (Steel, Browser Use,
   Safe Browsing) in explicit try/except that logs what failed and returns
   a typed error result — never swallow an exception and return an empty
   success-shaped object.
6. **Mock to unblock, then swap.** If a real dependency (Steel session,
   Browser Use run, Safe Browsing key) isn't available yet, hardcode a
   realistic fake response matching the exact contract shape, clearly
   marked `# MOCK — replace with real call`, so downstream work isn't
   blocked. Never let a mock silently become the shipped behavior — leave
   a TODO and mention it when handing off.
7. **Test before claiming done.** "Done" means you ran it and saw the
   expected output, not that the code looks right. For each step, state
   what you ran and what you observed before moving on.
8. **Commit small, commit often.** One commit per working step. Message
   format: `stepN: <what now works>`, e.g. `step2: steel scrape returns raw text`.
9. **Match existing style.** Once any file in a module exists, follow its
   naming, typing, and error-handling conventions rather than introducing a
   new pattern in the same folder.
10. **When genuinely blocked or ambiguous, ask — don't guess silently and
    keep going.** A wrong assumption compounds fast in a 24-hour build with
    three people working in parallel.

---

## 2. Architecture

```
/backend
  /agent        - Steel session creation + Browser Use task runner
  /classifier   - training script + saved model + predict function
  /safety       - Safe Browsing API wrapper
  /psych        - static JSON: dark-pattern category -> Cialdini principle -> explanation
  main.py       - FastAPI app, single POST /scan endpoint, orchestrates all three
  .env.example  - STEEL_API_KEY, SAFE_BROWSING_API_KEY, OPENAI_API_KEY
/frontend
  - Vite + React, one page: URL input -> "Run Scan" -> polls /scan -> renders
    trace log + flagged patterns + psych explanations + safety verdict
```

**Data flow for one scan:**
`URL in` → Steel scrapes page → classifier runs on scraped text → Safe
Browsing checks the URL → Browser Use attempts the cancel flow on the same
Steel session → orchestrator combines all four outputs into one `ScanReport`
→ frontend polls and renders it.

---

## 3. Interface contracts (frozen — change only with team agreement)

```python
# backend/agent -> main.py
class AgentStep(BaseModel):
    index: int
    action: str
    result: str
    friction: bool
    note: str

class AgentTrace(BaseModel):
    steps: list[AgentStep]
    outcome: Literal["cancelled", "blocked", "unclear"]

# backend/classifier + backend/psych -> main.py
class DarkPatternFlag(BaseModel):
    category: str
    confidence: float
    cialdini_principle: str
    explanation: str

class ClassifierResult(BaseModel):
    flags: list[DarkPatternFlag]

# backend/safety -> main.py
class SafetyVerdict(BaseModel):
    url: str
    malicious: bool
    threat_types: list[str]

# main.py -> frontend (POST /scan response)
class ScanReport(BaseModel):
    url: str
    safety: SafetyVerdict
    dark_patterns: ClassifierResult
    agent_trace: AgentTrace
    summary: str
```

Define these once (e.g. `backend/schemas.py`) and import everywhere — don't
redefine per module.

---

## 4. Environment

`.env.example` (commit this; never commit `.env`):
```
STEEL_API_KEY=
SAFE_BROWSING_API_KEY=
OPENAI_API_KEY=
```

`.gitignore` must include at minimum:
```
.env
__pycache__/
*.pkl
node_modules/
dist/
```

Backend: Python 3.11+, FastAPI, `uvicorn main:app --reload`.
Frontend: `npm create vite@latest` (React template), `npm run dev`.

---

## 5. Build order (do in this order; each step ends in something runnable)

1. **Scaffold.** Both folders, `.env.example`, `.gitignore` (ignoring `.env`).
   Push immediately so all three lanes branch from the same skeleton.
2. **Steel connection.** Minimal session: connect, call Steel's `/scrape` on
   a hardcoded test URL, return raw text. *Confirm this works before
   touching Browser Use.*
3. **Browser Use on top of Steel.** Same session, task: "navigate this site
   and attempt to cancel any subscription/trial, report each step and any
   friction point." Output must be an `AgentTrace`, not free text.
4. **Classifier.** Load the Mathur et al. dark-patterns dataset (bundle a
   CSV fallback for offline use). Train TF-IDF + LogisticRegression, save
   the model to disk. `predict(text) -> list[(category, confidence)]`.
5. **Safety.** `check_url(url) -> SafetyVerdict` wrapping Google Safe
   Browsing.
6. **Psych.** Static dict: category → Cialdini principle → one-sentence
   plain-English explanation. Function to enrich classifier output with it.
7. **Orchestration.** `POST /scan`: Steel scrape → classifier → safety
   check → Browser Use cancel-flow attempt → combine into `ScanReport`.
   Build this against mocked Lane A/B outputs first if they're not ready,
   so it isn't blocking or blocked.
8. **Frontend.** URL input → "Run Scan" → polling loading/trace view (the
   real call is slow — design for that) → final report card rendering
   `ScanReport`.

Do not start step *N+1* until step *N* has been run and its output verified.

---

## 6. Team lanes

Three people, three lanes, running in parallel against Section 3's contracts:

- **Lane A — Agent:** owns `/backend/agent`. Steps 2–3.
- **Lane B — Classifier/Safety/Psych:** owns `/backend/classifier`,
  `/backend/safety`, `/backend/psych`. Steps 4–6.
- **Lane C — Orchestration + Frontend:** owns `main.py` and `/frontend`.
  Steps 7–8, starting step 7 against mocks as soon as Section 3 is agreed.

Each person hands their AI this whole file plus their lane's step numbers
from Section 5. An AI assigned to a lane should not write code for another
lane's folder without being asked.

---

## 7. Definition of done for the demo

- `POST /scan` takes a real URL, runs all four pieces, returns a valid
  `ScanReport`.
- Frontend shows a live trace while the scan runs and a final report card
  after.
- At least one real "hard to cancel" test site produces a correct flag +
  Cialdini explanation + safety verdict, end to end, live.
- No `.env` values, API keys, or secrets appear anywhere in the git history.

## 8. Quick checklist before saying "this step is done"

- [ ] Did I run it, not just read it?
- [ ] Does the output match the frozen contract shape exactly?
- [ ] Are there try/except blocks around every external call?
- [ ] Are all secrets read from environment variables?
- [ ] Did I commit with a message naming the step?
- [ ] Did I stop here instead of continuing to the next step unasked?
