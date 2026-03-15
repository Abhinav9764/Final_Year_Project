import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  Activity,
  CheckCircle2,
  CircleAlert,
  Code2,
  Database,
  Loader2,
  MessageSquare,
  Moon,
  Paperclip,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Sparkles,
  StopCircle,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import "./App.css";

const PRIMARY_API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5001/api";
const API_CANDIDATES = [...new Set([
  PRIMARY_API,
  "http://localhost:5001/api",
  "http://127.0.0.1:5000/api",
  "http://localhost:5000/api",
])];
const HEALTH_TIMEOUT_MS = 2500;
const START_PIPELINE_TIMEOUT_MS = 30000;
const TOTAL_STEPS = 9;

const QUICK_PROMPTS = [
  "Build a chatbot trained on operating systems to answer support queries.",
  "Create a customer churn prediction model with explainable outputs.",
  "Develop an image classification API and interactive dashboard.",
];

const STEP_LABELS = {
  1: "Initialize",
  2: "Keyword Analysis",
  3: "Data Collection",
  4: "Keyword Confirmation",
  5: "Collection Complete",
  6: "Code Generation Dispatch",
  7: "Training and Build",
  8: "Deployment",
  9: "Completed",
};

function formatTime(ts) {
  if (!ts) return "";
  const date = new Date(ts * 1000);
  if (Number.isNaN(date.getTime())) return "";
  const base = date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const millis = String(Math.floor((ts % 1) * 1000)).padStart(3, "0");
  return `${base}.${millis}`;
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds) || 0);
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatStartError(err) {
  const serverMessage = err?.response?.data?.message;
  if (typeof serverMessage === "string" && serverMessage.trim()) {
    return serverMessage;
  }

  if (axios.isAxiosError(err)) {
    if (err.code === "ECONNABORTED") {
      return "Backend took too long to respond while starting the pipeline. Try again once the server is fully ready.";
    }
    if (!err.response) {
      return "Cannot reach backend API. Start backend on port 5001 (or set VITE_API_BASE_URL).";
    }
  }

  return err?.message || "Failed to start pipeline.";
}

function StageTimeline({ events, isRunning, hasError, filter, onFilterChange, progress, elapsedSec = 0 }) {
  const filteredEvents = useMemo(() => {
    if (filter === "active") {
      return events.filter((evt) => evt.status !== "done" && evt.status !== "error");
    }
    if (filter === "error") {
      return events.filter((evt) => evt.status === "error");
    }
    return events;
  }, [events, filter]);

  if (isRunning) {
    const latestEvent = events.length > 0 ? events[events.length - 1] : null;
    const currentMessage = latestEvent ? latestEvent.message : "Preparing tools...";
    return (
      <div className="inline-trace">
        <div className="processing-header">
          <Loader2 size={16} className="spin" />
          <span>{currentMessage} ({formatDuration(elapsedSec)})</span>
        </div>
        <div className="trace-progress">
          <div className="trace-progress-bar" style={{ width: `${progress}%` }} />
        </div>
      </div>
    );
  }

  return (
    <div className="inline-trace">
      <div className="processing-header">
        {hasError ? (
          <CircleAlert size={16} color="var(--danger)" />
        ) : (
          <CheckCircle2 size={16} color="var(--success)" />
        )}
        <span>{hasError ? "Pipeline failed" : "Completed processing"}</span>
      </div>

      <div className="trace-progress">
        <div className="trace-progress-bar" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

function DeploymentSummary({ summary }) {
  if (!summary) return null;

  return (
    <div className="inline-trace">
      <div className="processing-header">
        <Sparkles size={16} />
        <span>Deployment Overview</span>
      </div>
      <div className="kv-grid">
        <p><strong>Algorithm:</strong> {summary.algorithm_used || "N/A"}</p>
        <p><strong>Model:</strong> {summary.model_name || "N/A"}</p>
        <p><strong>Training Job:</strong> {summary.training_job_name || "N/A"}</p>
        <p><strong>Endpoint:</strong> {summary.endpoint_name || "N/A"}</p>
      </div>
      <div className="links-row" style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
        {summary.deploy_url && (
          <a className="primary-btn" href={summary.deploy_url} target="_blank" rel="noreferrer">
            Open App
          </a>
        )}
        {summary.endpoint_console_url && (
          <a className="ghost-btn" href={summary.endpoint_console_url} target="_blank" rel="noreferrer">
            SageMaker Console
          </a>
        )}
      </div>
    </div>
  );
}

function CollectedData({ data }) {
  if (!data || !data.top_results?.length) return null;

  return (
    <div className="inline-trace">
      <div className="processing-header">
        <Database size={16} />
        <span>Collected {data.count || 0} Records via {data.mode || "Search"}</span>
      </div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-soft)', margin: '0 0 12px' }}>
        Keywords: {(data.keywords || []).join(", ") || "N/A"}
      </p>
      <div className="data-list">
        {data.top_results.slice(0, 3).map((item, idx) => (
          <div key={`data-${idx}`} className="data-item">
            <p className="data-title">{item.title || "Untitled"}</p>
            <p className="data-meta">
              Relevance: {item.relevance ?? "N/A"}
              {item.url ? ` | ${item.url}` : item.ref ? ` | ${item.ref}` : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CodeOutput({ code }) {
  const [copied, setCopied] = useState("");

  if (!code) return null;

  const blocks = [
    ["app.py", code.app_py],
    ["test_app.py", code.test_py],
    ["index.html", code.html],
    ["style.css", code.css],
  ].filter(([, value]) => value && value.preview);

  const onCopy = async (label, text) => {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopied(label);
      window.setTimeout(() => setCopied(""), 1200);
    } catch {
      setCopied("");
    }
  };

  return (
    <div className="inline-trace">
      <div className="processing-header">
        <Code2 size={16} />
        <span>Generated Code Artifacts</span>
      </div>
      {blocks.map(([label, value]) => (
        <details className="code-block" key={label}>
          <summary>
            <span>{label} ({value.line_count} lines)</span>
            <button
              type="button"
              className="copy-btn"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onCopy(label, value.preview);
              }}
            >
              {copied === label ? "Copied" : "Copy"}
            </button>
          </summary>
          <pre>{value.preview}</pre>
        </details>
      ))}
    </div>
  );
}


export default function App() {
  const [theme, setTheme] = useState("dark");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([{ role: "assistant", text: "Enter a prompt to start the pipeline." }]);
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [running, setRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [serverOk, setServerOk] = useState(null);
  const [apiBase, setApiBase] = useState(API_CANDIDATES[0]);
  const [traceFilter, setTraceFilter] = useState("all");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [runStartedAt, setRunStartedAt] = useState(null);
  const [historyList, setHistoryList] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedFiles, setSelectedFiles] = useState([]);

  const chatBottomRef = useRef(null);
  const inputRef = useRef(null);
  const activeJobIdRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    const saved = localStorage.getItem("radml_theme");
    const nextTheme = saved === "light" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("radml_theme", theme);
  }, [theme]);

  const probeBackend = useCallback(async () => {
    const orderedBases = [apiBase, ...API_CANDIDATES.filter((base) => base !== apiBase)];
    for (const base of orderedBases) {
      try {
        await axios.get(`${base}/health`, { timeout: HEALTH_TIMEOUT_MS });
        setServerOk(true);
        if (base !== apiBase) {
          setApiBase(base);
        }
        return base;
      } catch {
        continue;
      }
    }
    setServerOk(false);
    return null;
  }, [apiBase]);

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      const result = await probeBackend();
      if (!active) return;
      if (!result) {
        setServerOk(false);
      }
    };
    checkHealth();
    const id = window.setInterval(checkHealth, 5000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [probeBackend]);

  const fetchHistory = useCallback(async () => {
    try {
      const activeApi = await probeBackend();
      if (activeApi) {
        const res = await axios.get(`${activeApi}/history`);
        if (res.data?.history) {
          setHistoryList(res.data.history);
        }
      }
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
  }, [probeBackend]);

  useEffect(() => {
    if (serverOk) {
      fetchHistory();
    }
  }, [serverOk, fetchHistory]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, events]);

  useEffect(() => {
    if (!running || !runStartedAt) return undefined;

    const tick = () => setElapsedSec(Math.floor((Date.now() - runStartedAt) / 1000));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [running, runStartedAt]);

  const latestEvent = events.length ? events[events.length - 1] : null;
  const latestStep = useMemo(
    () =>
      events.reduce((max, evt) => {
        if (typeof evt.step !== "number") return max;
        return evt.step > max ? evt.step : max;
      }, 0),
    [events]
  );
  const progress = useMemo(() => {
    if (latestStep <= 0) return 0;
    return Math.min(100, Math.round((latestStep / TOTAL_STEPS) * 100));
  }, [latestStep]);
  const currentStage = latestEvent?.message || (running ? "Pipeline running..." : "Ready for new prompt");

  const statusText = useMemo(() => {
    if (serverOk === null) return "Checking server...";
    if (serverOk === false) return "Backend offline";
    if (running) return "Pipeline running";
    return "Ready";
  }, [serverOk, running]);

  const clearSession = () => {
    if (running) return;
    setInput("");
    setSummary(null);
    setEvents([]);
    setErrorMsg("");
    setElapsedSec(0);
    setRunStartedAt(null);
    setSelectedFiles([]);
    setMessages([{ role: "assistant", text: "Session cleared. Enter a new prompt to run the pipeline." }]);
  };

  const applyQuickPrompt = (promptText) => {
    if (running) return;
    setInput(promptText);
    inputRef.current?.focus();
  };

  const loadHistoryItem = (item) => {
    if (running) return;
    setInput("");
    setRunning(false);
    setErrorMsg("");
    setElapsedSec(0);
    setRunStartedAt(null);
    setEvents([]);
    setSelectedFiles([]);

    const loadedMessages = [
      { role: "user", text: item.prompt }
    ];

    if (item.status === "done" && item.result) {
      loadedMessages.push({ role: "assistant", text: "Pipeline completed successfully.", summary: item.result });
      setSummary(item.result);
    } else {
      const errorText = item.result?.error || "Pipeline failed or incomplete.";
      loadedMessages.push({ role: "assistant", text: errorText, isError: true });
      setSummary(null);
    }

    setMessages(loadedMessages);
  };

  const handleSend = async (promptOverride) => {
    const prompt = (typeof promptOverride === "string" ? promptOverride : input).trim();
    if (!prompt || running) return;

    const activeApi = await probeBackend();
    if (!activeApi) {
      setErrorMsg("Backend is offline. Start the backend server and retry.");
      setMessages((prev) => [...prev, { role: "assistant", text: "Failed to start pipeline." }]);
      return;
    }

    setInput("");
    setRunning(true);
    setErrorMsg("");
    setSummary(null);
    setEvents([]);
    setTraceFilter("all");
    setElapsedSec(0);
    setRunStartedAt(Date.now());

    // Copy out the currently selected files, then immediately clear state
    const filesToUpload = [...selectedFiles];
    setSelectedFiles([]);

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: prompt,
        files: filesToUpload.map(f => f.name)
      },
      { role: "assistant", text: "Processing started..." }
    ]);

    try {
      let uploadedFilePaths = [];
      if (filesToUpload.length > 0) {
        setEvents([{ step: 0, status: "processing", message: "Uploading user files..." }]);
        const formData = new FormData();
        filesToUpload.forEach(file => formData.append("files", file));

        const uploadResp = await axios.post(`${activeApi}/upload`, formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });

        if (uploadResp.data && uploadResp.data.paths) {
          uploadedFilePaths = uploadResp.data.paths;
        }
      }

      const runResp = await axios.post(
        `${activeApi}/pipeline/run`,
        { prompt, uploaded_files: uploadedFilePaths },
        { timeout: START_PIPELINE_TIMEOUT_MS }
      );
      const jobId = runResp?.data?.job_id;
      if (!jobId) {
        throw new Error("Pipeline started but no job_id was returned.");
      }
      activeJobIdRef.current = jobId;

      const source = new EventSource(`${activeApi}/pipeline/stream/${encodeURIComponent(jobId)}`);
      let streamClosed = false;
      const closeStream = () => {
        if (streamClosed) return;
        streamClosed = true;
        source.close();
      };

      source.onmessage = ({ data }) => {
        let evt = null;
        try {
          evt = JSON.parse(data);
        } catch {
          return;
        }

        if (evt.status === "connected") return;

        setEvents((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.step === evt.step && last.status === evt.status && last.message === evt.message) {
            return prev;
          }
          return [...prev, evt];
        });

        if (evt.status === "error") {
          setRunning(false);
          setRunStartedAt(null);
          setErrorMsg(evt.message || "Pipeline failed.");

          setEvents((prevEvents) => {
            const errorText = evt.message || "Pipeline failed.";
            setMessages((prev) => [...prev, { role: "assistant", text: errorText, isError: true, traceEvents: prevEvents }]);
            return prevEvents;
          });

          closeStream();
          return;
        }

        if (evt.status === "done") {
          setRunning(false);
          setRunStartedAt(null);
          setSummary(evt);
          setMessages((prev) => [...prev, { role: "assistant", text: "Pipeline completed successfully.", summary: evt }]);
          closeStream();
          setTimeout(fetchHistory, 1000);
        }
      };

      source.onerror = () => {
        if (streamClosed) return;
        setRunning(false);
        setRunStartedAt(null);
        setErrorMsg("Stream disconnected. Check backend logs.");
        closeStream();
      };
    } catch (err) {
      setRunning(false);
      setRunStartedAt(null);
      setErrorMsg(formatStartError(err));
      if (axios.isAxiosError(err) && !err.response) {
        setServerOk(false);
      }
      setMessages((prev) => [...prev, { role: "assistant", text: "Failed to start pipeline." }]);
    }
  };

  const handleStop = async () => {
    if (!running || !activeJobIdRef.current) return;
    try {
      const activeApi = await probeBackend();
      if (activeApi) {
        await axios.post(`${activeApi}/pipeline/stop/${encodeURIComponent(activeJobIdRef.current)}`);
      }
    } catch (err) {
      console.error("Failed to stop job", err);
    }
  };

  const deleteHistory = async () => {
    try {
      const activeApi = await probeBackend();
      if (activeApi) {
        await axios.delete(`${activeApi}/history`);
      }
    } catch (e) {
      console.error("Failed to delete history", e);
    }
    setHistoryList([]);
  };

  const deleteHistoryItem = async (e, jobId) => {
    e.stopPropagation();
    try {
      const activeApi = await probeBackend();
      if (activeApi) {
        await axios.delete(`${activeApi}/history/${encodeURIComponent(jobId)}`);
      }
    } catch (err) {
      console.error("Failed to delete history item", err);
    }
    setHistoryList((prev) => prev.filter((item) => item.job_id !== jobId));
  };

  return (
    <div className={`app-shell ${sidebarOpen ? "has-sidebar" : ""}`}>
      <header className="topbar">
        <div className="brand">
          <button className="icon-btn toggle-sidebar" onClick={() => setSidebarOpen(!sidebarOpen)} title={sidebarOpen ? "Close sidebar" : "Open sidebar"}>
            {sidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
          </button>
          <div className="brand-name-wrap">
            <span className="brand-automodel">AutoModel</span>
            <p className="brand-status">{statusText}</p>
          </div>
        </div>

        <div className="topbar-actions">
          <span
            className={`server-pill ${serverOk === null ? "checking" : serverOk ? "online" : "offline"
              }`}
          >
            <Activity size={14} />
            {serverOk === null ? "Server Check" : serverOk ? "Server Online" : "Server Offline"}
          </span>
          <button type="button" className="ghost-btn session-clear-btn" onClick={clearSession} disabled={running}>
            <Trash2 size={16} /> Clear Session
          </button>
          <button
            type="button"
            className="theme-btn"
            onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
        </div>
      </header>

      <main className="workspace">
        {sidebarOpen && (
          <aside className="sidebar open">
            <div className="sidebar-header">
              <h3>Recent Chats</h3>
              <button
                type="button"
                className="sidebar-delete-btn"
                onClick={deleteHistory}
                title="Clear all chat history"
                disabled={historyList.length === 0}
              >
                <Trash2 size={14} />
              </button>
            </div>
            <div className="sidebar-content">
              {historyList.length === 0 ? (
                <p className="muted" style={{ padding: "16px", fontSize: "0.85rem" }}>No history yet.</p>
              ) : (
                historyList.map((item) => (
                  <div key={item.job_id} className="history-item-row">
                    <button
                      className="history-item"
                      onClick={() => loadHistoryItem(item)}
                    >
                      <MessageSquare size={14} className="history-icon" />
                      <span className="history-text">{item.prompt}</span>
                    </button>
                    <button
                      type="button"
                      className="history-item-del"
                      title="Delete this chat"
                      onClick={(e) => deleteHistoryItem(e, item.job_id)}
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>
        )}

        <section className="chat-panel">
          <div className="chat-log">

            {messages.length === 1 && (
              <div className="welcome-screen">
                <h2>Hello there.</h2>
                <h2 className="gradient-text">How can I help you build today?</h2>
                <div className="quick-prompts-card">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      type="button"
                      className="prompt-chip"
                      key={prompt}
                      onClick={() => applyQuickPrompt(prompt)}
                      disabled={running}
                    >
                      <Sparkles size={14} className="mr-2" />
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={`${msg.role}-${idx}`} className={`bubble ${msg.role === "user" ? "user" : "assistant"} ${msg.isError ? "error-bubble" : ""}`}>
                <div className="bubble-text">{msg.text}</div>

                {/* Show uploaded filenames in user bubble */}
                {msg.role === "user" && msg.files && msg.files.length > 0 && (
                  <div className="user-files-list">
                    {msg.files.map((fname, i) => (
                      <span key={i} className="user-file-chip">
                        <Paperclip size={12} /> {fname}
                      </span>
                    ))}
                  </div>
                )}

                {/* Embedded Final Results */}
                {msg.summary && (
                  <div className="assistant-widgets mt-2">
                    <DeploymentSummary summary={msg.summary} />
                    <CollectedData data={msg.summary.collected_data} />
                    <CodeOutput code={msg.summary.generated_code} />
                  </div>
                )}

                {/* Embedded Error Trace */}
                {msg.isError && msg.traceEvents && (
                  <div className="assistant-widgets mt-2">
                    <StageTimeline
                      events={msg.traceEvents}
                      isRunning={false}
                      hasError={true}
                      filter="all"
                      onFilterChange={() => { }}
                      progress={100}
                      elapsedSec={0}
                    />
                  </div>
                )}
              </div>
            ))}
            {running && (
              <div className="bubble assistant processing-bubble">
                <div className="bubble-text">Working on it...</div>
                <div className="assistant-widgets mt-2">
                  <StageTimeline
                    events={events}
                    isRunning={running}
                    hasError={Boolean(errorMsg)}
                    filter={traceFilter}
                    onFilterChange={setTraceFilter}
                    progress={progress}
                    elapsedSec={elapsedSec}
                  />
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          <div className="input-row-container">
            {/* Show staged files before sending */}
            {selectedFiles.length > 0 && (
              <div className="staged-files-row">
                {selectedFiles.map((f, idx) => (
                  <div className="staged-file-chip" key={`${f.name}-${idx}`}>
                    <span className="truncate">{f.name}</span>
                    <button type="button" onClick={() => setSelectedFiles(prev => prev.filter((_, i) => i !== idx))}>
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="input-row">
              <button
                type="button"
                className="attach-btn-circle"
                onClick={() => fileInputRef.current?.click()}
                disabled={running}
                title="Attach files (datasets, pdfs, txts)"
              >
                <Paperclip size={17} />
              </button>
              <input
                type="file"
                multiple
                style={{ display: "none" }}
                ref={fileInputRef}
                onChange={(e) => {
                  if (e.target.files) setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)]);
                  e.target.value = null; // reset Native input
                }}
              />
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Describe the ML model or chatbot you want to build..."
                disabled={running}
              />
              {running ? (
                <button type="button" className="send-btn stop-btn" onClick={handleStop} title="Stop Generation">
                  <StopCircle size={16} color="var(--danger)" />
                </button>
              ) : (
                <button type="button" className="send-btn" onClick={() => handleSend()} disabled={!input.trim()}>
                  <Send size={16} />
                </button>
              )}
            </div>
            {errorMsg && <p className="error-text text-center mt-2">{errorMsg}</p>}
          </div>
        </section>
      </main>
    </div>
  );
}
