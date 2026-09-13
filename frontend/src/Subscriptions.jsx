import { useEffect, useMemo, useState } from "react";

const POLL_MS = 900;

function formatEvent(event) {
  const { type, message, ...rest } = event;
  const text = message || "";
  if (text.includes("STEEL_API_KEY") || text.toLowerCase().includes("api key")) {
    return "We could not open this website right now. You can still use the step-by-step guide below.";
  }
  if (text.toLowerCase().includes("captcha") || text.toLowerCase().includes("login")) {
    return "This website needs you to sign in or complete a security check. We will pause and let you take over.";
  }
  if (type === "status" && text.toLowerCase().includes("starting")) return "Opening the cancellation steps…";
  if (type === "status" && text.toLowerCase().includes("opening")) return "Opening the cancellation page…";
  if (type === "complete") return text || "The cancellation help is finished.";
  if (type === "error") return "We could not finish this cancellation attempt. You can use the guide instead.";
  if (type === "agent_step") {
    const step = rest.step || {};
    return step.extracted || "Checking the next step…";
  }
  return text || "Working on the next step…";
}

function GymPlusDemo({ stage, cancelled, onStartCancel, onKeep, onLastClick, lastClickReady }) {
  const done = cancelled || stage === "done";
  return (
    <div className="gymplus-demo" aria-label="GymPlus cancellation page">
      <h3>GymPlus membership</h3>
      <p className="meta">Plan: Senior weekday · $29.99 / month</p>
      <p className={done ? "gymplus-complete" : undefined}>
        {done
          ? "Membership cancelled. You will not be billed again."
          : stage === "confirm"
            ? "Are you sure you want to cancel?"
            : "Your membership is active."}
      </p>
      {done ? null : stage === "confirm" ? (
        <p>
          <button type="button" className="secondary" onClick={onKeep}>
            Keep my plan
          </button>{" "}
          <button type="button" className="btn-accent" onClick={onLastClick} disabled={!lastClickReady}>
            Yes, cancel now
          </button>
        </p>
      ) : (
        <p>
          <button type="button" className="btn-accent" onClick={onStartCancel}>
            Cancel membership
          </button>
        </p>
      )}
    </div>
  );
}

function subRisk(item, plain) {
  if (item.status === "cancelled") {
    return { label: "Cancelled", level: "clear" };
  }
  if (item.recipe_id === "gymplus") {
    return { label: plain ? "Hard to cancel" : "Needs extra help to cancel", level: "severe" };
  }
  return { label: "Not checked yet", level: "caution" };
}

export function Subscriptions({ onAuthLost, plain }) {
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
  const [statusFilter, setStatusFilter] = useState("all");

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
          ? "No cancel link in the picture. We filled the GymPlus account page. Check the form, then Add subscription."
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

  async function completeGuide() {
    if (!guideFor) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/subscriptions/${guideFor.id}/guide/complete`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onAuthLost();
        return;
      }
      if (!res.ok) throw new Error(data.detail || "Could not complete the guide");
      await load();
      setGuide(null);
      setGuideFor(null);
      setChecked({});
      setStatusFilter("cancelled");
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
      ? "Please check the page, then approve the final step when you are ready."
      : "The website needs your help before we can continue.")
    : result
      ? result.cancelled
        ? "Your cancellation was completed."
        : result.needs_user_action
          ? "The website needs your help before we can continue."
          : "We could not finish this attempt. Please use the guide below."
      : job?.error
        ? "We could not finish this attempt. Please use the guide below."
        : null;
  const bannerOk =
    result?.cancelled ||
    job?.status === "needs_confirm" && result?.user_action_reason === "last_click";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <h1>My subscriptions</h1>
        {plain ? null : (
          <p className="lede">
            Take a screenshot or manually enter the subscription info to track
            them all in one list.
          </p>
        )}
      </div>

      {plain ? null : (
      <div className="tabs" role="tablist" aria-label="Filter by status">
        <button
          type="button"
          role="tab"
          aria-selected={statusFilter === "all"}
          className={statusFilter === "all" ? "tab on" : "tab"}
          onClick={() => setStatusFilter("all")}
        >
          All
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={statusFilter === "active"}
          className={statusFilter === "active" ? "tab on" : "tab"}
          onClick={() => setStatusFilter("active")}
        >
          In use
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={statusFilter === "cancelled"}
          className={statusFilter === "cancelled" ? "tab on" : "tab"}
          onClick={() => setStatusFilter("cancelled")}
        >
          Cancelled
        </button>
      </div>
      )}

      {statusFilter === "all" ? (
      <section
        className="upload-card"
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
        <div className="upload-card-head">
          <h2>{plain ? "Add one from a photo" : "Add from a screenshot"}</h2>
          {plain ? null : <span className="pill-note">Nothing is saved until you press Add</span>}
        </div>
        <p className="meta" style={{ fontSize: 18 }}>
          {plain
            ? "Send us a photo or screenshot of the bill. We read it and fill in the details for you to check."
            : "Upload a photo or screenshot of a receipt email, bank charge, or bill."}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
          <label className="file-picker">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#12203A" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 17V4" />
              <path d="M6.5 9.5L12 4l5.5 5.5" />
              <path d="M4 17v2.5h16V17" />
            </svg>
            {plain ? "Choose a photo" : "Choose a screenshot"}
            <input
              type="file"
              accept="image/png,image/jpeg,image/gif,image/webp"
              onChange={(event) => readFile(event.target.files?.[0])}
              style={{ display: "none" }}
            />
          </label>
          {preview ? (
            <img src={preview} alt="Screenshot to read" style={{ maxWidth: 140, maxHeight: 90, borderRadius: 10, border: "2px solid var(--line)" }} />
          ) : (
            <span className="meta">No file chosen yet</span>
          )}
          {preview ? (
            <button type="button" className="btn-secondary" onClick={extractScreenshot} disabled={extractBusy}>
              {extractBusy ? "Reading…" : "Read screenshot"}
            </button>
          ) : null}
        </div>

        {extractBusy ? (
          <div className="status-row">
            <span className="pulse-dot" />
            <span style={{ fontWeight: 600 }}>Reading the screenshot…</span>
          </div>
        ) : null}

        {extractNote ? <p className="ok-msg">{extractNote}</p> : null}

        <form className="draft-card" onSubmit={addItem}>
          <span style={{ fontWeight: 600, fontSize: 19 }}>Check these details, then add.</span>
          <div className="draft-grid">
            <label className="field" htmlFor="sub-name">
              Name
              <input id="sub-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label className="field" htmlFor="sub-cost">
              Cost
              <input id="sub-cost" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="optional" />
            </label>
            <label className="field" htmlFor="sub-renews">
              Renews
              <input id="sub-renews" value={renews} onChange={(e) => setRenews(e.target.value)} placeholder="optional" />
            </label>
            <label className="field" htmlFor="sub-url">
              Account or cancel page
              <input id="sub-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} required />
            </label>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            <button type="submit" className="btn-accent">Add subscription</button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setName("");
                setCost("");
                setRenews("");
                setUrl("https://example.com");
                setPreview("");
                setExtractNote("");
              }}
            >
              Start over
            </button>
          </div>
        </form>
      </section>
      ) : null}

      {error ? <p className="error" role="alert">{error}</p> : null}

      {items.length === 0 ? (
        <p className="meta">No subscriptions yet. Add one above.</p>
      ) : (
        (() => {
          const filteredItems = items.filter((item) =>
            statusFilter === "all"
              ? true
              : statusFilter === "cancelled"
                ? item.status === "cancelled"
                : item.status !== "cancelled"
          );
          if (filteredItems.length === 0) {
            return (
              <p className="meta">
                {statusFilter === "cancelled" ? "No cancelled subscriptions." : "No subscriptions in use."}
              </p>
            );
          }
          return filteredItems.map((item) => {
          const risk = subRisk(item, plain);
          return (
          <article className="sub-card" key={item.id}>
            <div className="sub-card-main">
              <div className="sub-card-title">
                <h2>{item.name}</h2>
                {plain ? null : <span className={`badge ${risk.level}`}>{risk.label}</span>}
              </div>
              {plain ? (
                <>
                  <p className="meta" style={{ fontSize: 22, fontWeight: 700, color: "var(--text)" }}>{item.cost || "Cost unknown"}</p>
                  {item.renews ? <p className="meta" style={{ fontSize: 22, fontWeight: 700, color: "var(--text)" }}>Next payment {item.renews}</p> : null}
                  <span className={`badge ${risk.level}`} style={{ alignSelf: "flex-start", fontSize: 18, fontWeight: 700, padding: "10px 16px" }}>{risk.label}</span>
                </>
              ) : (
                <p className="meta" style={{ fontSize: 17 }}>
                  {item.cost || "cost unknown"}
                  {item.renews ? ` · renews ${item.renews}` : ""}
                  {` · ${item.status}`}
                </p>
              )}
              {!plain && item.recipe_id !== "gymplus" ? (
                <p className="meta">The guide gives simple steps. Assisted help pauses when you need to take over.</p>
              ) : null}
              {item.last_outcome ? (
                <p style={plain ? { fontSize: 22, fontWeight: 700 } : undefined}>
                  {item.last_outcome === "Couldn't complete" ? "The last attempt could not be completed." : item.last_outcome}
                </p>
              ) : null}
            </div>
            <div className="sub-card-actions">
              {item.status === "cancelled" ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-secondary"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    textDecoration: "none",
                  }}
                >
                  Visit website
                </a>
              ) : (
                <>
                  <button
                    type="button"
                    className={guideFor?.id === item.id && guide ? "btn-primary active" : "btn-primary"}
                    onClick={() => openGuide(item)}
                    disabled={busy}
                  >
                    {busy && guideFor?.id === item.id ? "Opening guide…" : guideFor?.id === item.id && guide ? "Hide steps" : "Cancellation guide"}
                  </button>
                  <span className="or-divider">or</span>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => setPending(item)}
                    disabled={busy}
                  >
                    Assisted help to cancel
                  </button>
                </>
              )}
            </div>
          </article>
          );
          });
        })()
      )}

      {guide ? (
        <section className="guide-panel">
          <div className="guide-panel-head">
            <h3>Cancelling {guide.name}</h3>
            <button
              type="button"
              className="icon-btn"
              aria-label="Hide the steps"
              title="Hide the steps"
              onClick={() => setGuide(null)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FDF4DC" strokeWidth="2.4" strokeLinecap="round">
                <path d="M5 15l7-7 7 7" />
              </svg>
            </button>
          </div>
          <p>{guide.summary}</p>
          <p style={{ color: "#d8e2f2" }}>
            Check items off as you go. This list does not control the website.
          </p>
          <p>
            <a href={guide.url} target="_blank" rel="noreferrer" style={{ color: "#F9AC4F" }}>
              Open {guide.url} in your browser
            </a>
          </p>
          <ol>
            {(guide.steps || []).map((step) => (
              <li key={step.id} style={{ marginBottom: 4 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4, color: "#FDF4DC" }}>
                  <input
                    type="checkbox"
                    checked={Boolean(checked[step.id])}
                    onChange={(event) => {
                      const nextChecked = { ...checked, [step.id]: event.target.checked };
                      setChecked(nextChecked);
                      const allStepsChecked = (guide.steps || []).length > 0 &&
                        (guide.steps || []).every((guideStep) => nextChecked[guideStep.id]);
                      if (allStepsChecked) completeGuide();
                    }}
                  />
                  <strong>{step.title}</strong>
                </label>
                <div style={{ color: "#d8e2f2", fontSize: 15 }}>{step.detail}</div>
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
                You will still approve the final step.
              </>
            ) : (
              <>
                We will try to open the cancellation page and help with the
                steps. If the site needs your password or a security check, we
                will pause. You approve the final Cancel button.
              </>
            )}
            {" "}Confirm to start?
          </p>
          <p className="meta">{pending.url}</p>
          <p style={{ display: "flex", gap: 12 }}>
            <button type="button" className="btn-accent" onClick={confirmCancel} disabled={busy}>
              {busy ? "Starting…" : "Yes, cancel"}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setPending(null)}>
              Never mind
            </button>
          </p>
        </div>
      ) : null}

      {job ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <h2 style={{ margin: 0 }}>
              Cancellation help{" "}
              {job.status === "running" || job.status === "queued" ? "· in progress" : ""}
              {job.status === "needs_confirm" ? "· waiting for you" : ""}
            </h2>
            {job.status === "complete" ? (
              <button
                type="button"
                className="icon-btn on-light"
                aria-label="Close this"
                title="Close this"
                onClick={() => {
                  setJob(null);
                  setJobId(null);
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            ) : null}
          </div>
          {banner ? (
            <p className={bannerOk ? "ok-msg" : "error"}>{banner}</p>
          ) : null}
          {result?.user_action && !isGymDemo ? <p>{result.user_action}</p> : null}
          {isGymDemo ? (
            <GymPlusDemo
              stage={job?.status === "complete" && result?.cancelled ? "done" : gymStage}
              cancelled={Boolean(result?.cancelled)}
              lastClickReady={!busy && job?.status === "needs_confirm" && gymStage === "confirm"}
              onStartCancel={() => setGymStage("confirm")}
              onKeep={() => setGymStage("home")}
              onLastClick={confirmLastClick}
            />
          ) : null}
          {job.status === "needs_confirm" && !isGymDemo ? (
            <p>
              <button
                type="button"
                className="btn-accent"
                onClick={confirmLastClick}
                disabled={busy || !lastClickOk}
              >
                {busy
                  ? "Resuming…"
                  : result?.user_action_reason === "last_click"
                    ? "Yes, click the last Cancel button"
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
                View the helper session (about 2 minutes; may be view-only)
              </a>
            </p>
          ) : null}
          {!isGymDemo ? <pre className="trace">{traceText || "Waiting…"}</pre> : null}
        </section>
      ) : null}
    </div>
  );
}
