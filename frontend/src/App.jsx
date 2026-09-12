import { useEffect, useMemo, useState } from "react";
import { A11yToggle } from "./a11y.jsx";
import { Subscriptions } from "./Subscriptions.jsx";
import "./App.css";

const POLL_MS = 900;

function formatEvent(event) {
  const { type, message, ...rest } = event;
  if (type === "agent_step") {
    const step = rest.step || {};
    return `#${step.index ?? "?"} ${step.action || "step"} ${step.url || ""}\n${step.extracted || step.thought || step.error || ""}`;
  }
  const extras = Object.keys(rest)
    .filter((key) => !["at", "step", "patterns"].includes(key))
    .map((key) => `${key}=${JSON.stringify(rest[key])}`)
    .join(" ");
  return `[${type}] ${message || ""} ${extras}`.trim();
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
  const [tab, setTab] = useState("subs");
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
    } catch (err) {
      setError(err.message);
      setJob(null);
    }
  }

  async function runSteelLogin() {
    setDemoBusy(true);
    setError("");
    setDemoLogin(null);
    try {
      const res = await api("/demo/login", { method: "POST" });
      const data = await res.json();
      if (res.status === 401) {
        setUser(null);
        return;
      }
      setDemoLogin(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setDemoBusy(false);
    }
  }

  const report = job?.report;
  const traceText = useMemo(
    () => (job?.trace || []).map(formatEvent).join("\n\n"),
    [job]
  );

  if (!authReady) {
    return (
      <main className="shell">
        <p className="meta">Loading…</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="shell">
        <A11yToggle />
        <p className="eyebrow">Senior safety</p>
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
      </main>
    );
  }

  return (
    <main className="shell">
      <div className="topbar">
        <A11yToggle />
        <p className="meta signed-in">
          Signed in as {user}{" "}
          <button type="button" className="text-btn" onClick={signOut}>
            Sign out
          </button>
        </p>
      </div>
      <p className="eyebrow">Senior safety</p>
      <h1>Subscription Impossible</h1>
      <div className="tabs" role="tablist">
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
      </div>

      {tab === "subs" ? (
        <Subscriptions onAuthLost={() => setUser(null)} />
      ) : (
      <>
      <p className="lede">
        Paste a URL. We scrape it and rate <strong>Payment Safety</strong> — whether
        this snapshot looks like a risky place to type a card. That uses our
        wording model (Yamana data, Mathur 2019 categories) plus Safe Browsing.
        It is not an accessibility score.
      </p>

      <form className="row" onSubmit={runScan}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          type="url"
          required
        />
        <button type="submit" disabled={Boolean(running)}>
          {running ? "Scanning…" : "Run Scan"}
        </button>
      </form>
      <label className="toggle">
        <input
          type="checkbox"
          checked={skipAgent}
          onChange={(e) => setSkipAgent(e.target.checked)}
        />
        Skip old Browser Use path on scans (Cancel for me uses Playwright recipes)
      </label>

      <p>
        <button type="button" className="secondary" onClick={runSteelLogin} disabled={demoBusy}>
          {demoBusy ? "Running Steel login…" : "Run Steel login demo"}
        </button>
      </p>
      {demoLogin ? (
        <p className={demoLogin.ok ? "ok-msg" : "error"} role="status">
          {demoLogin.summary} {demoLogin.error || ""}
          {demoLogin.viewer_url ? (
            <>
              {" "}
              <a href={demoLogin.viewer_url} target="_blank" rel="noreferrer">
                Watch Steel session (about 2 minutes)
              </a>
            </>
          ) : null}
        </p>
      ) : null}

      {error ? <p className="error" role="alert">{error}</p> : null}

      <div className="grid">
        <section className="panel">
          <h2>Live scan trace {running ? "· in progress" : ""}</h2>
          <pre className="trace">{traceText || "Waiting for a scan."}</pre>
        </section>

        <section className="panel">
          <h2>Report</h2>
          {!report ? (
            <p className="meta">
              {running
                ? "This can take a while. This page polls until it finishes."
                : "No report yet."}
            </p>
          ) : (
            <ReportCard report={report} />
          )}
        </section>
      </div>
      </>
      )}
    </main>
  );
}

function ReportCard({ report }) {
  const safety = report.safety || {};
  const pay = report.payment_safety || {};
  const scrape = report.scrape || {};
  return (
    <div>
      <p>
        <span className={`badge ${pay.band_id || "unknown"}`}>{pay.band || "Payment safety unknown"}</span>{" "}
        <span className="meta">{report.url}</span>
      </p>
      <p className={scrape.ok ? "ok-msg" : "meta"}>
        Steel scrape: {scrape.ok ? `ok${scrape.title ? ` (${scrape.title})` : ""}` : scrape.error || "not run"}
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
          Google Safe Browsing did not run. Payment Safety still uses the page wording.
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
