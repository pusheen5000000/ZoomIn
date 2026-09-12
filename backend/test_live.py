"""Live API tests through localhost. Outbound Steel/Groq/SB happen on the server.

No human in the loop. Never prints API keys.
"""

from __future__ import annotations

import base64
import json
import re
import time
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8000"
fails: list[str] = []


def redact(text: str) -> str:
    t = str(text)
    t = re.sub(r"gsk_[A-Za-z0-9]+", "gsk_[redacted]", t)
    t = re.sub(r"ste-[A-Za-z0-9]+", "ste-[redacted]", t)
    t = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "sk-ant-[redacted]", t)
    t = re.sub(r"AIza[A-Za-z0-9_-]+", "AIza[redacted]", t)
    t = re.sub(r"key=[^&\s\"']+", "key=[redacted]", t)
    return t[:500]


def check(name: str, ok: bool, detail: str = "") -> None:
    msg = redact(detail)
    if ok:
        print(f"PASS  {name}" + (f"  {msg}" if msg else ""))
    else:
        fails.append(name)
        print(f"FAIL  {name}  {msg}")


def poll_job(client: httpx.Client, path: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        res = client.get(path)
        if res.status_code == 404:
            return {"status": "missing", "error": "404"}
        res.raise_for_status()
        last = res.json()
        if last.get("status") in {"complete", "error", "needs_confirm"}:
            return last
        time.sleep(1.2)
    last["status"] = last.get("status") or "timeout"
    return last


def fake_bill_png() -> tuple[str, str]:
    img = Image.new("RGB", (640, 240), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "GymPlus membership receipt", fill="black")
    draw.text((20, 80), "Amount: $29.99 / month", fill="black")
    draw.text((20, 120), "Renews: October 1, 2026", fill="black")
    draw.text((20, 160), "No cancel link in this email.", fill="black")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/png"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True) as client:
        h = client.get("/health")
        check("health", h.status_code == 200, h.text)

        bad = client.post("/auth/login", json={"username": "nope@x.com", "password": "x"})
        check("T9 bad login 401", bad.status_code == 401)

        login = client.post(
            "/auth/login",
            json={"username": "judge@demo.local", "password": "SeniorSafety2026"},
        )
        check("T1 login", login.status_code == 200, login.text)
        me = client.get("/auth/me")
        check("T1 session", me.status_code == 200 and me.json().get("authenticated") is True, me.text)

        gym = client.post(
            "/subscriptions/",
            json={"name": "GymPlus", "url": "https://example.com", "cost": "$29.99", "renews": "Oct 1"},
        )
        check("T2 add GymPlus", gym.status_code == 200, gym.text)
        gym_id = gym.json().get("id") if gym.status_code == 200 else None
        check("T2 GymPlus recipe", (gym.json() or {}).get("recipe_id") == "gymplus")

        nflix = client.post(
            "/subscriptions/",
            json={"name": "Netflix", "url": "https://www.netflix.com", "cost": "$15.99"},
        )
        check("T2 add Netflix", nflix.status_code == 200, nflix.text)
        nflix_id = nflix.json().get("id") if nflix.status_code == 200 else None
        check("T2 Netflix recipe generic", (nflix.json() or {}).get("recipe_id") == "generic")

        listing = client.get("/subscriptions/")
        check("T2 list has rows", listing.status_code == 200 and len(listing.json().get("subscriptions") or []) >= 2)

        if nflix_id:
            guide = client.post(f"/subscriptions/{nflix_id}/guide", timeout=10.0)
            gj = guide.json() if guide.status_code == 200 else {}
            check("T3 guide HTTP", guide.status_code == 200, redact(guide.text))
            steps = gj.get("steps") or []
            check("T3 guide has steps", len(steps) >= 5)
            check("T3 you_click present", any(s.get("id") == "you_click" for s in steps))
            check("T3 guide does not visit", gj.get("visits_site") is False)
            check("T3 no scrape", not gj.get("scrape_ok"))

        b64, mime = fake_bill_png()
        ext = client.post(
            "/subscriptions/extract",
            json={"image_base64": b64, "media_type": mime},
            timeout=60.0,
        )
        ej = ext.json() if ext.headers.get("content-type", "").startswith("application/json") else {}
        check("T7 extract HTTP", ext.status_code == 200, redact(ext.text))
        check("T7 extract ok or clear error", bool(ej.get("ok") or ej.get("error")))
        fields = ej.get("fields") or {}
        url = fields.get("url") or ""
        check("T7 no invented non-http URL", url == "" or url.lower().startswith("http"))
        print("      provider=", ej.get("provider"), "fields=", {k: fields.get(k) for k in ("name", "url", "cost", "renews")})

        scan = client.post("/scan", json={"url": "https://example.com", "skip_agent": True, "include_a11y": False})
        check("T6 scan start", scan.status_code == 200, scan.text)
        scan_id = (scan.json() or {}).get("scan_id")
        job = poll_job(client, f"/scan/{scan_id}", timeout=100) if scan_id else {}
        check("T6 scan finished", job.get("status") == "complete", job.get("error") or job.get("status"))
        report = job.get("report") or {}
        pay = report.get("payment_safety") or {}
        check("T6 payment_safety present", bool(pay.get("band")), json.dumps(pay)[:200])
        check("T6 no senior score in report", "Easier for seniors" not in json.dumps(report))
        scrape = report.get("scrape") or {}
        print("      scrape.ok=", scrape.get("ok"), "title=", scrape.get("title"), "pay=", pay.get("band"))
        sb = (report.get("safety") or {}).get("verdict")
        print("      safebrowsing verdict=", sb)
        traces = json.dumps(job.get("trace") or [])
        check("T9 scan did not start Browser Use", "Browser Use starting" not in traces)

        if gym_id:
            cancel = client.post(
                f"/subscriptions/{gym_id}/cancel",
                json={"confirmed": True},
                timeout=30.0,
            )
            check("T4 gymplus cancel start", cancel.status_code == 200, cancel.text)
            cj = cancel.json() if cancel.status_code == 200 else {}
            cjob = poll_job(client, f"/subscriptions/jobs/{cj.get('job_id')}", timeout=120) if cj.get("job_id") else {}
            check(
                "T4 gymplus paused or complete",
                cjob.get("status") in {"needs_confirm", "complete"},
                cjob.get("status") + " " + redact(str(cjob.get("error") or (cjob.get("result") or {}).get("summary"))),
            )
            result = cjob.get("result") or {}
            traces = json.dumps(cjob.get("trace") or [])
            check("T4 not Browser Use", "Browser Use starting" not in traces)
            check("T4 not SSL CDP browser-use error", "CERTIFICATE_VERIFY_FAILED" not in traces)
            if cjob.get("status") == "needs_confirm" and cj.get("job_id"):
                cont = client.post(f"/subscriptions/jobs/{cj['job_id']}/confirm")
                check("T4 confirm HTTP", cont.status_code == 200, cont.text)
                cjob2 = poll_job(client, f"/subscriptions/jobs/{cj['job_id']}", timeout=60)
                r2 = cjob2.get("result") or {}
                check(
                    "T4 gymplus cancelled or still paused",
                    bool(r2.get("cancelled") or cjob2.get("status") == "needs_confirm"),
                    redact(str(r2.get("summary") or cjob2.get("status"))),
                )
                print("      gymplus cancelled=", r2.get("cancelled"), "summary=", redact(str(r2.get("summary"))))

        if nflix_id:
            ncan = client.post(
                f"/subscriptions/{nflix_id}/cancel",
                json={"confirmed": True},
                timeout=30.0,
            )
            check("T5 netflix cancel start", ncan.status_code == 200, ncan.text)
            nj = ncan.json() if ncan.status_code == 200 else {}
            njob = poll_job(client, f"/subscriptions/jobs/{nj.get('job_id')}", timeout=120) if nj.get("job_id") else {}
            nres = njob.get("result") or {}
            check(
                "T5 netflix paused not silent fail",
                njob.get("status") in {"needs_confirm", "complete", "error"},
                redact(str(njob.get("status")) + " " + str(nres.get("summary") or njob.get("error"))),
            )
            if njob.get("status") == "needs_confirm":
                check(
                    "T5 handoff copy",
                    bool(nres.get("user_action") or nres.get("summary")),
                    redact(str(nres.get("user_action") or nres.get("summary"))),
                )
                print("      reason=", nres.get("user_action_reason"), "step=", nres.get("step_id"))
            traces = json.dumps(njob.get("trace") or [])
            check("T5 not Browser Use", "Browser Use starting" not in traces)
            check("T5 did not auto-claim Netflix cancelled without confirm", not (nres.get("cancelled") and njob.get("status") == "complete" and nres.get("user_action_reason") != "last_click"))

    print()
    if fails:
        print(f"{len(fails)} failed:", ", ".join(fails))
        raise SystemExit(1)
    print("all live checks passed")


if __name__ == "__main__":
    main()
