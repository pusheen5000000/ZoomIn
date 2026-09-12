import { useEffect, useMemo, useState } from "react";
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

export default function App() {
  const [url, setUrl] = useState("https://example.com");
  const [skipAgent, setSkipAgent] = useState(false);
  const [scanId, setScanId] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const running = job && (job.status === "queued" || job.status === "running");

  useEffect(() => {
    if (!scanId) return undefined;
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch(`/scan/${scanId}`);
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

  async function runScan(event) {
    event.preventDefault();
    setError("");
    setJob({ status: "queued", trace: [], url });
    try {
      const res = await fetch("/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, skip_agent: skipAgent }),
      });
      if (!res.ok) throw new Error(`Scan failed (${res.status})`);
      const data = await res.json();
      setScanId(data.scan_id);
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

  return (
    <main className="shell">
      <p className="eyebrow">Dark-pattern recon</p>
      <h1>Subscription Impossible</h1>
      <p className="lede">
        Paste a URL. We scrape it, classify manipulative copy, check Safe Browsing,
        then send an agent to try canceling anything that looks like a subscription.
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
        Skip cancel-flow agent (faster, classifier + safety only)
      </label>

      {error ? <p className="error">{error}</p> : null}

      <div className="grid">
        <section className="panel">
          <h2>Live agent trace {running ? "· in progress" : ""}</h2>
          <pre className="trace">{traceText || "Waiting for a scan."}</pre>
        </section>

        <section className="panel">
          <h2>Report</h2>
          {!report ? (
            <p className="meta">
              {running
                ? "The cancel-flow agent can take a few minutes. This page polls until it finishes."
                : "No report yet."}
            </p>
          ) : (
            <ReportCard report={report} />
          )}
        </section>
      </div>
    </main>
  );
}

function ReportCard({ report }) {
  const safety = report.safety || {};
  const verdict = safety.verdict || "unknown";
  return (
    <div>
      <p>
        <span className={`badge ${verdict}`}>{verdict}</span>{" "}
        <span className="meta">{report.url}</span>
      </p>
      {safety.error ? <p className="meta">Safety: {safety.error}</p> : null}

      {(report.patterns || []).length === 0 ? (
        <p className="meta">No dark-pattern categories crossed the confidence bar.</p>
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

      <h2>Cancel-flow agent</h2>
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
