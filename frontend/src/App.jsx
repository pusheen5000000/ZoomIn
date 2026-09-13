import { useEffect, useMemo, useState } from "react";
import { A11yToggle } from "./a11y.jsx";
import { Subscriptions } from "./Subscriptions.jsx";
import "./App.css";

const POLL_MS = 900;

function formatEvent(event) {
  const { type, message, ...rest } = event;
  const text = message || "";
  if (text.includes("STEEL_API_KEY") || text.toLowerCase().includes("api key")) {
    return "We could not open this website right now. Please try again later, or use the guide below to cancel it yourself.";
  }
  if (text.toLowerCase().includes("captcha") || text.toLowerCase().includes("login")) {
    return "This website needs you to sign in or complete a security check. We will not do that for you.";
  }
  if (type === "status" && text.toLowerCase().includes("opening")) return "Opening the website…";
  if (type === "status" && text.toLowerCase().includes("loading")) return "Looking at the website…";
  if (text.toLowerCase().includes("recipe") || text.toLowerCase().includes("browser")) {
    return "Starting careful cancellation help…";
  }
  if (type === "complete") return text || "Website check finished.";
  if (type === "error") return "We could not finish checking this website. Please try again.";
  if (type === "agent_step") {
    const step = rest.step || {};
    return step.extracted || "Checking the next part of the website…";
  }
  if (type === "safety") return "Checking whether this website has been reported as unsafe…";
  if (type === "classifier") return "Looking for confusing or pressuring wording…";
  return text || "Checking the website…";
}

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "include", ...options });
  return res;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [url, setUrl] = useState("https://example.com");
  const [skipAgent, setSkipAgent] = useState(true);
  const [scanId, setScanId] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [loginUser, setLoginUser] = useState("judge@demo.local");
  const [loginPass, setLoginPass] = useState("SeniorSafety2026");
  const [demoLogin, setDemoLogin] = useState(null);
  const [demoBusy, setDemoBusy] = useState(false);
  const [tab, setTab] = useState("home");
  const [subsCount, setSubsCount] = useState(null);
  const [scansRun, setScansRun] = useState(0);
  const running = job && (job.status === "queued" || job.status === "running");

  useEffect(() => {
    let cancelled = false;
    api("/auth/me")
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && data.authenticated) setUser(data.username);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setAuthReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    api("/subscriptions/")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setSubsCount((data.subscriptions || []).length);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [user, tab]);

  useEffect(() => {
    if (!scanId) return undefined;
    let cancelled = false;
    async function poll() {
      try {
        const res = await api(`/scan/${scanId}`);
        if (res.status === 401) {
          setUser(null);
          return;
        }
        if (res.status === 404) {
          if (!cancelled) {
            setError(
              "That scan is gone. The API restarted and jobs live only in memory. Click Run Scan again."
            );
            setScanId(null);
          }
          return;
        }
        if (!res.ok) throw new Error(`Poll failed (${res.status})`);
        const data = await res.json();
        if (!cancelled) setJob(data);
        if (data.status === "complete" || data.status === "error") return;
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
      if (!cancelled) window.setTimeout(poll, POLL_MS);
    }
    poll();
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  async function signIn(event) {
    event.preventDefault();
    setError("");
    const res = await api("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: loginUser, password: loginPass }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Could not sign in");
      return;
    }
    setUser(data.username);
  }

  async function signOut() {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
    setScanId(null);
    setJob(null);
    setDemoLogin(null);
  }

  async function runScan(event) {
    event.preventDefault();
    setError("");
    setJob({ status: "queued", trace: [], url });
    try {
      const res = await api("/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          skip_agent: skipAgent,
          include_a11y: false,
        }),
      });
      if (res.status === 401) {
        setUser(null);
        throw new Error("Please sign in again");
      }
      if (!res.ok) throw new Error(`Scan failed (${res.status})`);
      const data = await res.json();
      setScanId(data.scan_id);
      setScansRun((n) => n + 1);
    } catch (err) {
      setError(err.message);
      setJob(null);
    }
  }

  const report = job?.report;
  const traceText = useMemo(
    () => (job?.trace || []).map(formatEvent).join("\n\n"),
    [job]
  );

  if (!authReady) {
    return (
      <main className="app-shell">
        <p className="meta" style={{ padding: 32 }}>Loading…</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="app-shell">
        <div className="login-shell">
          <img
            src="/brand/zoomin-wordmark.png"
            alt="ZoomIn"
            className="brand-wordmark"
            style={{ height: 44, marginBottom: 28 }}
          />
          <p className="eyebrow">Subscription safety</p>
          <h1>Sign in</h1>
          <p className="lede">
            Use the demo account from the README. This is not a real email. Your
            session stays active if you refresh.
          </p>
          <form className="login-form" onSubmit={signIn}>
            <label htmlFor="login-user">Email</label>
            <input
              id="login-user"
              type="email"
              autoComplete="username"
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              required
            />
            <label htmlFor="login-pass">Password</label>
            <input
              id="login-pass"
              type="password"
              autoComplete="current-password"
              value={loginPass}
              onChange={(e) => setLoginPass(e.target.value)}
              required
            />
            <button type="submit">Sign in</button>
          </form>
          {error ? <p className="error" role="alert">{error}</p> : null}
          <p className="meta">Demo: judge@demo.local / SeniorSafety2026</p>
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="brand">
          <img src="/brand/zoomin-wordmark.png" alt="ZoomIn" className="brand-wordmark" />
          <span className="brand-tag">Subscription safety</span>
        </div>
        <div className="header-actions">
          <A11yToggle />
          <span className="signed-in-label">
            Signed in as <strong>{user}</strong>{" "}
            <button type="button" className="text-btn" onClick={signOut}>
              Sign out
            </button>
          </span>
        </div>
      </header>

      <main className="shell">
        <nav className="tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "home"}
            className={tab === "home" ? "tab on" : "tab"}
            onClick={() => setTab("home")}
          >
            Home
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "subs"}
            className={tab === "subs" ? "tab on" : "tab"}
            onClick={() => setTab("subs")}
          >
            My subscriptions
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "scan"}
            className={tab === "scan" ? "tab on" : "tab"}
            onClick={() => setTab("scan")}
          >
            Scan a site
          </button>
        </nav>

        {tab === "home" ? (
          <div className="home-grid">
            <section className="hero">
              <div className="hero-copy">
                <h1>We zoom in so you don’t have to.</h1>
                <p>
                  ZoomIn keeps a list of every subscription you have, and
                  checks a website's wording before you type your card into
                  it. It never clicks a final Cancel or Pay button for you.
                </p>
              </div>
              <div className="hero-mark">
                <img src="/brand/zoomin-owl.png" alt="" />
              </div>
            </section>

            <section className="month-panel">
              <div className="month-panel-head">
                <h2>At a glance</h2>
              </div>
              <div className="chip-row">
                <span className="chip">
                  {subsCount === null
                    ? "Loading subscriptions…"
                    : subsCount === 0
                      ? "No subscriptions tracked yet"
                      : `${subsCount} subscription${subsCount === 1 ? "" : "s"} tracked`}
                </span>
                <span className="chip">
                  {scansRun === 0 ? "No sites scanned yet" : `${scansRun} site${scansRun === 1 ? "" : "s"} scanned this session`}
                </span>
              </div>
            </section>
          </div>
        ) : null}

        {tab === "subs" ? (
          <Subscriptions onAuthLost={() => setUser(null)} />
        ) : null}

        {tab === "scan" ? (
        <>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
          <h1>Scan a site</h1>
          <p className="lede">
            Enter a website address and we will look for signs that could make
            paying or cancelling confusing. We will explain what we find in
            simple language. This is helpful information, not a guarantee that
            a website is safe.
          </p>
        </div>

        <form className="row" onSubmit={runScan}>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            type="url"
            required
          />
          <button type="submit" disabled={Boolean(running)}>
            {running ? "Scanning…" : "Run scan"}
          </button>
        </form>
        <label className="toggle">
          <input
            type="checkbox"
            checked={skipAgent}
            onChange={(e) => setSkipAgent(e.target.checked)}
          />
          Use the slower, more careful website check
        </label>

        <p className="meta">We never ask you to share your password or security code.</p>

        {error ? <p className="error" role="alert">{error}</p> : null}

        {!job ? (
          <p className="status-row" style={{ background: "var(--panel)", border: "2px solid var(--line)" }}>
            <span className="meta">No scan run yet. Paste a URL above and press Run scan.</span>
          </p>
        ) : (
        <div className="grid">
          <section className="panel outline">
            <h2>Is this website safe to pay on? {running ? "· checking…" : ""}</h2>
            {running ? (
              <div className="status-row">
                <span className="pulse-dot" />
                <span style={{ fontWeight: 600 }}>Reading the page, checking the wording, asking Safe Browsing…</span>
              </div>
            ) : null}
            {!report ? (
              !running ? <p className="meta">No report yet.</p> : null
            ) : (
              <ReportCard report={report} />
            )}
          </section>

          <section className="panel">
            <h2>What we are checking {running ? "· in progress" : ""}</h2>
            <pre className="trace">{traceText || "Waiting for a scan."}</pre>
          </section>
        </div>
        )}
        </>
        ) : null}
      </main>

      <footer className="site-footer">
        <p className="foot-note">ZoomIn never bypasses a sign-in, a security check, or your final confirmation.</p>
        <span className="foot-links">Help · Privacy · Contact a human</span>
      </footer>
    </div>
  );
}

function ReportCard({ report }) {
  const safety = report.safety || {};
  const pay = report.payment_safety || {};
  const scrape = report.scrape || {};
  return (
    <div>
      <p>
        <span className={`badge ${pay.band_id || "unknown"}`}>{pay.band || "Website safety is not known yet"}</span>{" "}
        <span className="meta">{report.url}</span>
      </p>
      <p className={scrape.ok ? "ok-msg" : "meta"}>
        Website reading: {scrape.ok ? `finished${scrape.title ? ` (${scrape.title})` : ""}` : "not available right now"}
      </p>
      {pay.band ? (
        <div className={`score-card ${pay.band_id || "unknown"}`}>
          <p className="score-band">{pay.band}</p>
          <p className="meta">{pay.disclaimer}</p>
          {(pay.reasons || []).length ? (
            <ul className="score-breakdown">
              {pay.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p className="meta">No extra payment-trap wording stood out on this snapshot.</p>
          )}
          <p className="meta">{pay.source}</p>
        </div>
      ) : null}
      {safety.verdict === "error" ? (
        <p className="meta">
          We could not complete the website safety check, but the wording review is still available.
        </p>
      ) : null}

      <h2>Billing and cancel flags</h2>
      {(report.senior_flags || []).length === 0 ? (
        <p className="meta">No extra page checks on this snapshot.</p>
      ) : (
        (report.senior_flags || []).map((flag) => (
          <article className="pattern" key={flag.id}>
            <strong>{flag.plain_language}</strong>
            <div className="meta">
              {flag.kind === "classifier" ? "wording model" : "page check"}
              {typeof flag.confidence === "number"
                ? ` · ${Math.round(flag.confidence * 100)}%`
                : ""}
            </div>
            {flag.evidence ? <p className="meta">Seen: {flag.evidence}</p> : null}
          </article>
        ))
      )}

      <h2>Wording categories</h2>
      {(report.patterns || []).length === 0 ? (
        <p className="meta">No wording categories crossed the confidence bar.</p>
      ) : (
        report.patterns.map((pattern) => (
          <article className="pattern" key={pattern.category}>
            <strong>
              {pattern.category} · {(pattern.confidence * 100).toFixed(0)}%
            </strong>
            <div className="meta">{pattern.cialdini_principle}</div>
            <p>{pattern.explanation}</p>
          </article>
        ))
      )}

      <h2>Browser steps</h2>
      <p>{report.agent?.summary}</p>
      {report.agent?.friction_points?.length ? (
        <ul className="friction">
          {report.agent.friction_points.map((point, index) => (
            <li key={index}>
              <strong>{point.severity || "note"}:</strong> {point.description || point}
            </li>
          ))}
        </ul>
      ) : (
        <p className="meta">No structured friction points returned.</p>
      )}
    </div>
  );
}
