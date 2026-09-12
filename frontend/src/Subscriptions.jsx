import { useEffect, useMemo, useState } from "react";

const POLL_MS = 900;

function formatEvent(event) {
  const { type, message, ...rest } = event;
  if (type === "agent_step") {
    const step = rest.step || {};
    return `#${step.index ?? "?"} ${step.action || "step"} ${step.url || ""}\n${step.extracted || step.thought || step.error || ""}`;
  }
  const extras = Object.keys(rest)
    .filter((key) => !["at", "step"].includes(key))
    .map((key) => `${key}=${JSON.stringify(rest[key])}`)
    .join(" ");
  return `[${type}] ${message || ""} ${extras}`.trim();
}

function GymPlusDemo({ stage, cancelled, onStartCancel, onKeep, onLastClick, lastClickReady }) {
  const done = cancelled || stage === "done";
  return (
    <div className="gymplus-demo" aria-label="GymPlus demo page">
      <h3>GymPlus membership</h3>
      <p className="meta">Plan: Senior weekday · $29.99 / month · fake demo</p>
      <p className={done ? "ok-msg" : undefined}>
        {done
          ? "Membership cancelled. You will not be billed again."
          : stage === "confirm"
            ? "Are you sure you want to cancel?"
            : "Your membership is active."}
      </p>
      {done ? null : stage === "confirm" ? (
        <p>
          <span className="warn-inline">Wait — you will lose your discount. Are you sure?</span>
          <br />
          <button type="button" className="secondary" onClick={onKeep}>
            Keep my plan
          </button>{" "}
          <button type="button" onClick={onLastClick} disabled={!lastClickReady}>
            Yes, cancel now
          </button>
        </p>
      ) : (
        <p>
          <button type="button" onClick={onStartCancel}>
            Cancel membership
          </button>
        </p>
      )}
    </div>
  );
}

export function Subscriptions({ onAuthLost }) {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("GymPlus");
  const [url, setUrl] = useState("https://example.com");
  const [cost, setCost] = useState("");
  const [renews, setRenews] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [extractBusy, setExtractBusy] = useState(false);
  const [extractNote, setExtractNote] = useState("");
  const [preview, setPreview] = useState("");
  const [guide, setGuide] = useState(null);
  const [guideFor, setGuideFor] = useState(null);
  const [checked, setChecked] = useState({});
  const [gymStage, setGymStage] = useState("home");

  async function load() {
    const res = await fetch("/subscriptions/", { credentials: "include" });
    if (res.status === 401) {
      onAuthLost();
      return;
    }
    if (!res.ok) throw new Error("Could not load subscriptions");
    const data = await res.json();
    setItems(data.subscriptions || []);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!jobId) return undefined;
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch(`/subscriptions/jobs/${jobId}`, { credentials: "include" });
        if (res.status === 401) {
          onAuthLost();
          return;
        }
        if (res.status === 404) {
          if (!cancelled) {
            setError("That cancel job is gone. The API restarted.");
            setJobId(null);
          }
          return;
        }
        if (!res.ok) throw new Error(`Poll failed (${res.status})`);
        const data = await res.json();
        if (!cancelled) setJob(data);
        if (data.status === "complete" || data.status === "error") {
          load().catch(() => {});
          return;
        }
        // needs_confirm: keep polling so the log stays live, but do not loop forever if stuck — still poll.
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
      if (!cancelled) window.setTimeout(poll, POLL_MS);
    }
    poll();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  async function addItem(event) {
    event.preventDefault();
    setError("");
    const res = await fetch("/subscriptions/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url, cost, renews }),
    });
    if (res.status === 401) {
      onAuthLost();
      return;
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setError(data.detail || "Could not add");
      return;
    }
    setName("");
    setCost("");
    setRenews("");
    setExtractNote("");
    setPreview("");
    await load();
  }

  function readFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      setError("Use a PNG, JPEG, GIF, or WebP screenshot.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPreview(String(reader.result || ""));
    reader.readAsDataURL(file);
  }

  async function extractScreenshot(event) {
    event.preventDefault();
    if (!preview) {
      setError("Choose or paste a screenshot first.");
      return;
    }
    setError("");
    setExtractBusy(true);
    try {
      const comma = preview.indexOf(",");
      const header = preview.slice(0, comma);
      const media =
        (header.match(/data:(image\/[a-zA-Z0-9.+-]+)/) || [])[1] || "image/png";
      const res = await fetch("/subscriptions/extract", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: preview.slice(comma + 1),
          media_type: media,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onAuthLost();
        return;
      }
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || data.detail || "Could not read screenshot");
      }
      const fields = data.fields || {};
      if (fields.name) setName(fields.name);
      if (fields.url) setUrl(fields.url);
      if (fields.cost) setCost(fields.cost);
      if (fields.renews) setRenews(fields.renews);
      setExtractNote(
        data.url_from_recipe
          ? "No cancel link in the picture. Filled the known GymPlus demo URL. Check the form, then Add subscription."
          : `Check the form, then Add subscription. Nothing is saved yet${data.provider ? ` (read with ${data.provider})` : ""}.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setExtractBusy(false);
    }
  }

  async function openGuide(item) {
    setError("");
    setBusy(true);
    setGuide(null);
    setGuideFor(item);
    setChecked({});
    try {
      const res = await fetch(`/subscriptions/${item.id}/guide`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onAuthLost();
        return;
      }
      if (!res.ok) throw new Error(data.detail || "Could not build a guide");
      setGuide(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmCancel() {
    if (!pending) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/subscriptions/${pending.id}/cancel`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onAuthLost();
        return;
      }
      if (!res.ok) throw new Error(data.detail || `Cancel failed (${res.status})`);
      setJobId(data.job_id);
      setJob({ status: "queued", trace: [], name: pending.name, recipe_id: pending.recipe_id });
      setGymStage("home");
      setPending(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmLastClick() {
    if (!jobId) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/subscriptions/jobs/${jobId}/confirm`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onAuthLost();
        return;
      }
      if (!res.ok) throw new Error(data.detail || `Confirm failed (${res.status})`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const traceText = useMemo(
    () => (job?.trace || []).map(formatEvent).join("\n\n"),
    [job]
  );
  const result = job?.result;
  const isGymDemo = result?.demo === "gymplus" || job?.recipe_id === "gymplus";
  const lastClickOk =
    !isGymDemo || gymStage === "confirm" || job?.status === "complete";
  const banner = job?.status === "needs_confirm"
    ? (result?.user_action_reason === "last_click"
      ? "Needs your confirmation"
      : `Stuck at ${result?.step_id || "a step"} — needs your input`)
    : result
      ? result.cancelled
        ? "Cancelled successfully"
        : result.needs_user_action
          ? `Stuck at ${result.step_id || "a step"} — needs your input`
          : "Couldn't complete — here's what happened"
      : job?.error
        ? "Couldn't complete"
        : null;
  const bannerOk =
    result?.cancelled ||
    job?.status === "needs_confirm" && result?.user_action_reason === "last_click";

  return (
    <div>
      <p className="lede">
        Add a subscription by typing, or upload a screenshot of an email or bill.
        We fill the form for you to check — we do not save until you click Add
        subscription.         You can add any site. <strong>Guide me</strong> is a checklist on your
        own device. <strong>GymPlus</strong> semi-assisted cancel is a fake page
        in this app. On a live site, semi-assisted cancel opens Steel Chrome
        and usually pauses at login or CAPTCHA — we do not bypass those. Last
        Cancel click still needs your confirm.
      </p>

      <div
        className="panel"
        style={{ marginBottom: 16 }}
        onPaste={(event) => {
          const item = [...(event.clipboardData?.items || [])].find((entry) =>
            entry.type.startsWith("image/")
          );
          if (item) {
            event.preventDefault();
            readFile(item.getAsFile());
          }
        }}
      >
        <h2>Add by screenshot</h2>
        <p className="meta">
          Upload or paste an image. Uses your Groq key (already in .env). If you
          later add ANTHROPIC_API_KEY, Claude is used first.
        </p>
        <input
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          onChange={(event) => readFile(event.target.files?.[0])}
        />
        {preview ? (
          <p>
            <img src={preview} alt="Screenshot to read" style={{ maxWidth: "100%", maxHeight: 180 }} />
          </p>
        ) : null}
        <p>
          <button type="button" className="secondary" onClick={extractScreenshot} disabled={extractBusy}>
            {extractBusy ? "Reading…" : "Read screenshot into the form"}
          </button>
        </p>
        {extractNote ? <p className="ok-msg">{extractNote}</p> : null}
      </div>

      <form className="login-form" onSubmit={addItem}>
        <h2>Review and add</h2>
        <label htmlFor="sub-name">Name</label>
        <input
          id="sub-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <label htmlFor="sub-url">Account or cancel page URL</label>
        <input
          id="sub-url"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
        <label htmlFor="sub-cost">Cost (optional)</label>
        <input id="sub-cost" value={cost} onChange={(e) => setCost(e.target.value)} />
        <label htmlFor="sub-renews">Renews (optional)</label>
        <input
          id="sub-renews"
          value={renews}
          onChange={(e) => setRenews(e.target.value)}
        />
        <button type="submit">Add subscription</button>
      </form>

      {error ? <p className="error" role="alert">{error}</p> : null}

      {items.length === 0 ? (
        <p className="meta">No subscriptions yet. Add one above.</p>
      ) : (
        items.map((item) => (
          <article className="pattern sub-row" key={item.id}>
            <strong>{item.name}</strong>
            <div className="meta">
              {item.cost || "cost unknown"}
              {item.renews ? ` · renews ${item.renews}` : ""}
              {` · ${item.status}`}
            </div>
            <p className="meta">
              {item.recipe_id === "gymplus"
                ? "GymPlus fake page in this app. Semi-assisted cancel does not use Steel."
                : "Guide me is a checklist only. Semi-assisted cancel would try Steel and usually get blocked (login/CAPTCHA)."}
            </p>
            {item.last_outcome ? <p>{item.last_outcome}</p> : null}
            <p>
              <button
                type="button"
                onClick={() => openGuide(item)}
                disabled={busy}
              >
                {busy && guideFor?.id === item.id ? "Opening guide…" : "Guide me"}
              </button>{" "}
              <button
                type="button"
                className="secondary"
                onClick={() => setPending(item)}
                disabled={item.status === "cancelled" || busy}
              >
                Semi-assisted cancel
              </button>
            </p>
            {(item.log || []).length ? (
              <ul className="friction">
                {item.log.slice(-5).reverse().map((entry, index) => (
                  <li key={index}>
                    {entry.at}: {entry.outcome}
                    {entry.summary ? ` — ${entry.summary}` : ""}
                  </li>
                ))}
              </ul>
            ) : null}
          </article>
        ))
      )}

      {guide ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Cancel guide for {guide.name}</h2>
          <p>{guide.summary}</p>
          <p className="meta">
            Check items off as you go. This list does not control the website.
          </p>
          <p>
            <a href={guide.url} target="_blank" rel="noreferrer">
              Open {guide.url} in your browser
            </a>
          </p>
          <ol className="friction">
            {(guide.steps || []).map((step) => (
              <li key={step.id} style={{ marginBottom: 12 }}>
                <label className="toggle" style={{ marginBottom: 4 }}>
                  <input
                    type="checkbox"
                    checked={Boolean(checked[step.id])}
                    onChange={(event) =>
                      setChecked((prev) => ({ ...prev, [step.id]: event.target.checked }))
                    }
                  />
                  <strong>{step.title}</strong>
                </label>
                <div className="meta">{step.detail}</div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {pending ? (
        <div className="score-card poor" role="dialog" aria-labelledby="confirm-cancel-title">
          <p id="confirm-cancel-title" className="score-band">
            About to cancel {pending.name}
          </p>
          <p>
            {pending.recipe_id === "gymplus" ? (
              <>
                GymPlus is a <strong>fake</strong> membership. The cancel page
                opens in this app — not Netflix, not Steel. You still confirm
                the last click.
              </>
            ) : (
              <>
                Playwright will open a Steel tab on the live URL, pause on
                blockers, and will not click the last Cancel until you confirm.
                Live sites often block cloud Chrome.
              </>
            )}
            {" "}Confirm to start?
          </p>
          <p className="meta">{pending.url}</p>
          <p>
            <button type="button" onClick={confirmCancel} disabled={busy}>
              {busy ? "Starting…" : "Yes, try to cancel"}
            </button>{" "}
            <button type="button" className="secondary" onClick={() => setPending(null)}>
              Never mind
            </button>
          </p>
        </div>
      ) : null}

      {job ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>
            Semi-assisted cancel{" "}
            {job.status === "running" || job.status === "queued" ? "· in progress" : ""}
            {job.status === "needs_confirm" ? "· waiting for you" : ""}
          </h2>
          {banner ? (
            <p className={bannerOk ? "ok-msg" : "error"}>{banner}</p>
          ) : null}
          {result?.user_action ? <p>{result.user_action}</p> : null}
          {isGymDemo ? (
            <GymPlusDemo
              stage={job?.status === "complete" && result?.cancelled ? "done" : gymStage}
              cancelled={Boolean(result?.cancelled)}
              lastClickReady={!busy && job?.status === "needs_confirm"}
              onStartCancel={() => setGymStage("confirm")}
              onKeep={() => setGymStage("home")}
              onLastClick={confirmLastClick}
            />
          ) : null}
          {job.status === "needs_confirm" ? (
            <p>
              <button
                type="button"
                onClick={confirmLastClick}
                disabled={busy || !lastClickOk}
              >
                {busy
                  ? "Resuming…"
                  : result?.user_action_reason === "last_click"
                    ? isGymDemo && gymStage !== "confirm"
                      ? "Click Cancel membership on the demo first"
                      : "Yes, click the last Cancel button"
                    : "I've done that step, continue"}
              </button>
            </p>
          ) : null}
          {result?.summary ? <p>{result.summary}</p> : null}
          {result?.page_url ? (
            <p>
              <a href={result.page_url} target="_blank" rel="noreferrer">
                Open this page on your own device
              </a>
            </p>
          ) : null}
          {result?.viewer_url ? (
            <p>
              <a href={result.viewer_url} target="_blank" rel="noreferrer">
                Watch Steel session (about 2 minutes; may be view-only)
              </a>
            </p>
          ) : null}
          <pre className="trace">{traceText || "Waiting…"}</pre>
        </section>
      ) : null}
    </div>
  );
}
