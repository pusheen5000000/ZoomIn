"""Deterministic login demo inside a Steel Cloud Chrome tab.

Steel cannot reach localhost, so we inject a local HTML login form into the
remote page and fill the README demo account with Playwright.
"""

from __future__ import annotations

from typing import Any

from config import DEMO_PASSWORD, DEMO_USER
from nav.steel_playwright import open_steel_page, session_info

DEMO_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Member sign in</title>
  <style>
    body { font-family: Georgia, serif; background: #1a1a1a; color: #eee; padding: 40px; }
    label { display: block; margin: 12px 0 4px; }
    input { font-size: 16px; padding: 8px; width: 280px; }
    button { margin-top: 16px; padding: 8px 16px; }
    .ok { color: #8f8; font-size: 22px; }
    .err { color: #f88; }
  </style>
</head>
<body>
  <h1>Account sign in</h1>
  <form id="login-form">
    <label for="username">Email</label>
    <input id="username" name="username" type="email" autocomplete="username" />
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" />
    <button id="submit" type="submit">Sign in</button>
  </form>
  <p id="status"></p>
  <script>
    document.getElementById("login-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const user = document.getElementById("username").value;
      const pass = document.getElementById("password").value;
      const status = document.getElementById("status");
      if (user === "USER_PLACEHOLDER" && pass === "PASS_PLACEHOLDER") {
        status.className = "ok";
        status.textContent = "Welcome. You are signed in.";
        document.body.dataset.signedIn = "true";
      } else {
        status.className = "err";
        status.textContent = "That email or password is wrong.";
        document.body.dataset.signedIn = "false";
      }
    });
  </script>
</body>
</html>
"""


async def run_login_demo() -> dict[str, Any]:
    steps: list[dict[str, str]] = []
    html = DEMO_LOGIN_HTML.replace("USER_PLACEHOLDER", DEMO_USER).replace(
        "PASS_PLACEHOLDER", DEMO_PASSWORD
    )

    async with open_steel_page() as (session, page):
        info = session_info(session)
        steps.append({"action": "open_steel_session", "detail": info["session_id"] or ""})
        await page.set_content(html, wait_until="domcontentloaded")
        steps.append({"action": "show_login_form", "detail": "Injected demo sign-in page"})
        await page.fill("#username", DEMO_USER)
        steps.append({"action": "fill_username", "detail": DEMO_USER})
        await page.fill("#password", DEMO_PASSWORD)
        steps.append({"action": "fill_password", "detail": "(hidden)"})
        await page.click("#submit")
        await page.wait_for_selector("#status.ok", timeout=8_000)
        signed_in = await page.locator("body").get_attribute("data-signed-in")
        steps.append({"action": "submit", "detail": "Signed in" if signed_in == "true" else "Failed"})
        return {
            "ok": signed_in == "true",
            "summary": "Playwright signed in with the demo account on a Steel browser.",
            "steps": steps,
            **info,
        }
