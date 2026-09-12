"""Offline checks only. No Steel, Groq, Anthropic, Safe Browsing, or live websites."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT.parent / "frontend" / "src"
fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"PASS  {name}")
    else:
        fails.append(name)
        print(f"FAIL  {name}  {detail}")


def main() -> None:
    from nav.blockers import classify_html
    from nav.recipe_player import lookup_recipe, recipe_id_for
    from psych.explain import enrich
    from score.payment import payment_assessment
    from subscriptions.extract import _parse_json
    from subscriptions.guide import _base_steps, build_guide
    from subscriptions import store
    from detect.heuristics import scan_dom_and_text
    from detect.a11y import map_violations
    from config import DEMO_PASSWORD, DEMO_USER
    from auth import LoginBody, login
    from unittest.mock import MagicMock

    # T1 static: subscriptions tab first
    app_jsx = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    check("T1 default tab is subs", 'useState("subs")' in app_jsx)
    check("T1 My subscriptions button appears before Scan in source", app_jsx.find("My subscriptions") < app_jsx.find("Scan a site"))
    check("T1 no Include accessibility scan checkbox", "Include accessibility scan" not in app_jsx)
    check("T1 Payment Safety copy", "Payment Safety" in app_jsx)
    check("T1 skip Browser Use default true", "useState(true)" in app_jsx)

    # T2 recipe ids
    check("T2 GymPlus -> gymplus", recipe_id_for("https://example.com", "GymPlus") == "gymplus")
    check("T2 Netflix -> generic", recipe_id_for("https://www.netflix.com", "Netflix") == "generic")
    check("T2 Spotify -> generic", recipe_id_for("https://www.spotify.com", "Spotify") == "generic")
    check("T2 lookup does not invent Netflix URL", lookup_recipe("Netflix", "") is None)
    check("T2 lookup keeps Netflix URL", lookup_recipe("Netflix", "https://www.netflix.com")["url"] == "https://www.netflix.com")
    item_g = store.add("t", name="GymPlus", url="https://example.com", recipe_id=recipe_id_for("https://example.com", "GymPlus"))
    item_n = store.add("t", name="Netflix", url="https://www.netflix.com", recipe_id=recipe_id_for("https://www.netflix.com", "Netflix"))
    check("T2 store two rows", len(store.list_for("t")) == 2)
    check("T2 gymplus recipe on row", item_g["recipe_id"] == "gymplus")
    check("T2 generic recipe on row", item_n["recipe_id"] == "generic")

    # T3 guide steps (no scrape)
    steps = _base_steps("Netflix", "https://www.netflix.com")
    ids = [s["id"] for s in steps]
    check("T3 guide has you_click", "you_click" in ids)
    check("T3 guide says user signs in", any("password" in s["detail"].lower() for s in steps))
    check("T3 guide mentions Netflix URL", any("netflix.com" in s["detail"].lower() for s in steps))
    g = build_guide("Netflix", "https://www.netflix.com")
    check("T3 guide does not visit", g.get("visits_site") is False)
    check("T3 Netflix path hint", any(s.get("id") == "site_path" for s in g["steps"]))
    check("T3 no scrape fields", "scrape_ok" not in g and "payment_safety" not in g)

    # T4/T5 blockers + pause semantics
    check("T4/T5 captcha named", classify_html('<iframe src="https://www.google.com/recaptcha/x">', "")["kind"] == "captcha")
    check("T4/T5 2FA named", classify_html("", "Enter the verification code we sent")["kind"] == "2FA")
    check("T4/T5 payment named", classify_html("", "Card number and CVV")["kind"] == "payment_field")
    check("T4/T5 bot named", classify_html("", "Sorry, unusual traffic from your computer")["kind"] == "bot_check")
    check("T4/T5 clean page not blocked", classify_html("<p>Hello</p>", "Welcome to Example Domain") is None)
    sub = (FRONTEND / "Subscriptions.jsx").read_text(encoding="utf-8")
    check("T4/T5 continue button copy", "I've done that step, continue" in sub)
    check("T4/T5 last click copy", "Yes, click the last Cancel button" in sub)
    check("T4 GymPlus demo lives in the app", "GymPlusDemo" in sub)
    check("T4/T5 no bypass claim", "Do not bypass" in sub or "do not bypass" in sub.lower() or "We do not bypass" in sub)

    import asyncio
    from nav.recipe_player import HELD, finish_recipe, start_recipe

    gdemo = asyncio.run(start_recipe("offline-gym", "gymplus"))
    check("T4 gymplus demo flag", gdemo.get("demo") == "gymplus" and gdemo.get("paused") is True)
    check("T4 gymplus does not open Steel", gdemo.get("viewer_url") in (None, ""))
    fdemo = asyncio.run(finish_recipe("offline-gym"))
    check("T4 gymplus finish cancels", fdemo.get("cancelled") is True)
    check("T4 gymplus held released", "offline-gym" not in HELD)

    # T6 payment safety (local heuristics + fake SB)
    clean = payment_assessment([], [], {"verdict": "safe", "malicious": False})
    check("T6 clean band good", clean["band_id"] == "good")
    sneaky = payment_assessment(
        [{"category": "Sneaking", "confidence": 0.9}],
        [],
        {"verdict": "safe", "malicious": False},
    )
    check("T6 sneaking not good", sneaky["band_id"] in {"ok", "poor"})
    malware = payment_assessment([], [], {"verdict": "unsafe", "malicious": True})
    check("T6 malware poor", malware["band_id"] == "poor")
    html = '<a href="/cancel" style="font-size:1px">cancel</a> You must call to cancel. Limited time offer.'
    flags = scan_dom_and_text(html, "You must call to cancel. Limited time offer.")
    ids_f = {f["id"] for f in flags}
    check("T6 call_to_cancel heuristic", "call_to_cancel" in ids_f)
    check("T6 fake_urgency heuristic", "fake_urgency" in ids_f)
    mapped = map_violations({"violations": [{"id": "color-contrast", "impact": "serious", "nodes": [{}]}]})
    check("T6 axe mapper still works locally", mapped and mapped[0]["kind"] == "a11y")
    check("T6 report UI has no Senior Safety Score", "Senior Safety Score" not in app_jsx)
    check("T6 report UI has no score-number 100/100 a11y", "page accessibility" not in app_jsx.lower())

    # T7 screenshot JSON parse — no model call
    parsed = _parse_json('here {"name": "Netflix", "url": "not-a-url", "cost": "$15", "renews": "monthly"}')
    check("T7 drops invented non-http URL", parsed["url"] == "" and parsed["name"] == "Netflix")
    parsed2 = _parse_json('{"name": "GymPlus", "url": "https://example.com", "cost": "$29", "renews": "Oct"}')
    check("T7 keeps real http URL", parsed2["url"].startswith("https://"))
    check("T7 enrich drops Not Dark Pattern", enrich([{"category": "Not Dark Pattern", "confidence": 0.9}]) == [])
    check("T7 enrich keeps Urgency", len(enrich([{"category": "Urgency", "confidence": 0.9}])) == 1)

    # T8 in-memory jobs vanish conceptually
    job = store.new_job("t", item_n)
    check("T8 job stored", store.CANCEL_JOBS.get(job["job_id"]) is not None)
    store.CANCEL_JOBS.clear()
    check("T8 job gone after clear (API restart analogue)", store.CANCEL_JOBS.get(job["job_id"]) is None)

    # T9 auth demo + no Browser Use in cancel path
    check("T9 demo user constant", DEMO_USER == "judge@demo.local")
    check("T9 demo password constant", DEMO_PASSWORD == "SeniorSafety2026")
    req = MagicMock()
    req.session = {}
    try:
        login(LoginBody(username="wrong@x.com", password="nope"), req)
        check("T9 bad login rejected", False)
    except Exception as exc:
        check("T9 bad login rejected", getattr(exc, "status_code", None) == 401 or "wrong" in str(exc).lower())
    login(LoginBody(username="judge@demo.local", password="SeniorSafety2026"), req)
    check("T9 good login sets session", req.session.get("username") == DEMO_USER)
    player = (ROOT / "nav" / "recipe_player.py").read_text(encoding="utf-8")
    check("T9 recipe player not browser-use", "browser_use" not in player.lower() and "from browser" not in player)
    check("T9 subscriptions router not ACT_CANCEL_TASK", "ACT_CANCEL_TASK" not in (ROOT / "subscriptions" / "router.py").read_text())

    # local classifier if trained (still offline)
    model = ROOT / "classifier" / "models" / "dark_patterns.joblib"
    if model.exists():
        from classifier.predict import predict

        preds = predict("Hurry! Only 2 left in stock. Offer expires in 5 minutes.")
        check("T6 local classifier runs", isinstance(preds, list))
    else:
        print("SKIP  T6 classifier model missing")

    print()
    if fails:
        print(f"{len(fails)} failed:", ", ".join(fails))
        raise SystemExit(1)
    print("all offline checks passed")


if __name__ == "__main__":
    main()
