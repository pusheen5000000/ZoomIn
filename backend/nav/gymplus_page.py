"""Injected GymPlus cancel page. Steel cannot load localhost."""

GYMPLUS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>GymPlus — membership</title>
  <style>
    body { font-family: Georgia, serif; background: #1a1a1a; color: #eee; padding: 40px; max-width: 40rem; }
    button { font-size: 18px; padding: 10px 16px; margin: 8px 8px 0 0; }
    .warn { color: #fc6; }
    .ok { color: #8f8; font-size: 22px; }
    #confirm-panel { display: none; margin-top: 24px; }
    body[data-stage="confirm"] #confirm-panel { display: block; }
  </style>
</head>
<body data-stage="home" data-cancelled="false">
  <h1>GymPlus membership</h1>
  <p>Plan: Senior weekday · $29.99 / month</p>
  <p id="status">Your membership is active.</p>
  <button id="start-cancel" type="button">Cancel membership</button>
  <div id="confirm-panel">
    <p class="warn">Wait — you will lose your discount. Are you sure?</p>
    <button id="keep" type="button">Keep my plan</button>
    <button id="confirm-cancel" type="button">Yes, cancel now</button>
  </div>
  <script>
    document.getElementById("start-cancel").onclick = () => {
      document.body.dataset.stage = "confirm";
      document.getElementById("status").textContent = "Are you sure you want to cancel?";
    };
    document.getElementById("keep").onclick = () => {
      document.body.dataset.stage = "home";
      document.getElementById("status").textContent = "Your membership is still active.";
    };
    document.getElementById("confirm-cancel").onclick = () => {
      document.body.dataset.cancelled = "true";
      document.body.dataset.stage = "done";
      document.getElementById("status").className = "ok";
      document.getElementById("status").textContent = "Membership cancelled. You will not be billed again.";
      document.getElementById("confirm-panel").style.display = "none";
    };
  </script>
</body>
</html>
"""
