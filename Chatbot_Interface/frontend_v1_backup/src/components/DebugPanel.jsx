/**
 * DebugPanel.jsx  (v7 — NEW)
 * ============================
 * System health / debug panel — calls GET /api/debug and shows
 * a colour-coded checklist of all APIs, packages, and connectivity.
 */
import { useState } from "react";
import { apiUrl } from "../lib/api.js";

const STATUS_COLORS = {
  ok:      { bg: "#0d2b1a", border: "#22c55e", dot: "#22c55e", text: "#86efac" },
  warning: { bg: "#2b1f07", border: "#f59e0b", dot: "#f59e0b", text: "#fcd34d" },
  error:   { bg: "#2b0d0d", border: "#ef4444", dot: "#ef4444", text: "#fca5a5" },
};

const OVERALL_LABEL = {
  ok:      "✓ All Systems Operational",
  warning: "⚠ Some Warnings",
  error:   "✗ Issues Detected — Fix Before Running",
};

export default function DebugPanel({ token }) {
  const [report,  setReport]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const runDebug = async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(apiUrl('/debug'), { headers });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      setReport(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const overall = report?.overall_status || "ok";
  const oc      = STATUS_COLORS[overall] || STATUS_COLORS.ok;

  return (
    <div style={{
      background: "#0d0d1a", border: "1px solid #2a2a4a",
      borderRadius: 10, padding: 20, marginTop: 16, fontFamily: "monospace",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: "#a78bfa" }}>
          🔬 System Debugger
        </span>
        <button
          onClick={runDebug}
          disabled={loading}
          style={{
            background: loading ? "#1e1e3a" : "#4c1d95",
            color: "#e4e4f0", border: "none", borderRadius: 6,
            padding: "5px 14px", cursor: loading ? "not-allowed" : "pointer",
            fontSize: 12, fontWeight: 600,
          }}
        >
          {loading ? "Running checks…" : "Run Diagnostics"}
        </button>
        {report && (
          <span style={{
            background: oc.bg, border: `1px solid ${oc.border}`,
            borderRadius: 6, padding: "3px 10px",
            color: oc.text, fontSize: 12, fontWeight: 600,
          }}>
            {OVERALL_LABEL[overall]}
          </span>
        )}
      </div>

      {error && (
        <div style={{
          background: "#2b0d0d", border: "1px solid #ef4444",
          borderRadius: 6, padding: 10, color: "#fca5a5", fontSize: 12,
        }}>
          ✗ {error}
        </div>
      )}

      {report && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {report.checks.map((chk, i) => {
            const c = STATUS_COLORS[chk.status] || STATUS_COLORS.warning;
            return (
              <div key={i} style={{
                background: c.bg, border: `1px solid ${c.border}`,
                borderRadius: 6, padding: "7px 12px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: c.dot, flexShrink: 0,
                  }} />
                  <span style={{ color: "#c4c4e0", fontSize: 12, fontWeight: 600, minWidth: 180 }}>
                    {chk.name}
                  </span>
                  <span style={{ color: c.text, fontSize: 12 }}>{chk.message}</span>
                </div>
                {chk.fix && (
                  <div style={{
                    marginTop: 4, marginLeft: 16,
                    color: "#9494bb", fontSize: 11,
                    whiteSpace: "pre-wrap", lineHeight: 1.5,
                  }}>
                    💡 {chk.fix}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!report && !loading && (
        <div style={{ color: "#5a5a8a", fontSize: 12 }}>
          Click "Run Diagnostics" to check all API credentials, packages, and connectivity.
        </div>
      )}
    </div>
  );
}
