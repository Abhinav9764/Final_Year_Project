"""
app_ui.py
=========
RAD-ML — Standalone Flask Visualisation UI

A self-contained web interface to submit a research prompt and watch
the RL agent collect data in real-time via Server-Sent Events (SSE).

This file is INDEPENDENT of main.py — it directly calls the same
brain / collectors / core / utils modules and streams every agent
log event live to the browser.

Usage:
    pip install flask flask-cors
    python app_ui.py
    → Open http://localhost:5000 in your browser
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, Response, jsonify, render_template_string, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Global SSE queue per session (simple single-user demo)
# ---------------------------------------------------------------------------
_event_queue: queue.Queue = queue.Queue()


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"


class _QueueHandler(logging.Handler):
    """Push every log record into the SSE queue for live streaming."""

    LEVEL_COLOUR = {
        "DEBUG":    "#6b7280",
        "INFO":     "#22d3ee",
        "WARNING":  "#fbbf24",
        "ERROR":    "#f87171",
        "CRITICAL": "#ef4444",
    }

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        _event_queue.put({
            "type":    "log",
            "level":   record.levelname,
            "colour":  self.LEVEL_COLOUR.get(record.levelname, "#fff"),
            "message": msg,
            "time":    record.asctime if hasattr(record, "asctime") else "",
        })


# ---------------------------------------------------------------------------
# HTML template (single-file, no external templates dir needed)
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>RAD-ML — Data Collection Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #0d1117;
      --surface:   #161b22;
      --border:    #30363d;
      --accent:    #7c3aed;
      --accent2:   #06b6d4;
      --text:      #e6edf3;
      --muted:     #8b949e;
      --success:   #22d3ee;
      --warning:   #fbbf24;
      --error:     #f87171;
      --radius:    12px;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    /* ---- Header ---- */
    header {
      width: 100%;
      padding: 20px 40px;
      display: flex;
      align-items: center;
      gap: 14px;
      background: linear-gradient(135deg, #1e1b4b 0%, #0d1117 60%);
      border-bottom: 1px solid var(--border);
    }

    .logo {
      width: 42px; height: 42px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 18px; color: #fff;
      box-shadow: 0 0 20px rgba(124,58,237,0.4);
    }

    header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
    header p  { font-size: 13px; color: var(--muted); margin-top: 2px; }

    .badge {
      margin-left: auto;
      background: rgba(124,58,237,0.15);
      border: 1px solid rgba(124,58,237,0.4);
      color: #a78bfa;
      border-radius: 20px;
      padding: 4px 14px;
      font-size: 12px;
      font-weight: 600;
    }

    /* ---- Main layout ---- */
    main {
      width: 100%;
      max-width: 1100px;
      padding: 32px 24px;
      display: grid;
      grid-template-columns: 1fr 1.6fr;
      gap: 24px;
    }

    @media (max-width: 800px) {
      main { grid-template-columns: 1fr; }
    }

    /* ---- Cards ---- */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }

    .card-header {
      padding: 16px 20px 14px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 10px;
      font-size: 13px; font-weight: 600; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.8px;
    }

    .card-header .dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 6px var(--accent);
    }

    /* ---- Input panel ---- */
    .input-panel { padding: 20px; }

    label {
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: var(--muted);
      margin-bottom: 8px;
    }

    textarea {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      padding: 12px 14px;
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      resize: vertical;
      min-height: 100px;
      outline: none;
      transition: border-color 0.2s;
    }
    textarea:focus { border-color: var(--accent); }

    .row { display: flex; gap: 12px; margin-top: 14px; align-items: flex-end; }

    .field { flex: 1; }
    .field label { margin-bottom: 6px; }

    select, input[type="number"] {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      padding: 10px 12px;
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    select:focus, input[type="number"]:focus { border-color: var(--accent); }

    .btn-run {
      padding: 11px 28px;
      background: linear-gradient(135deg, var(--accent), #6d28d9);
      color: #fff;
      border: none;
      border-radius: 8px;
      font-family: 'Inter', sans-serif;
      font-weight: 600;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
      box-shadow: 0 0 20px rgba(124,58,237,0.35);
    }
    .btn-run:hover { transform: translateY(-1px); box-shadow: 0 4px 24px rgba(124,58,237,0.5); }
    .btn-run:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    /* ---- Stats strip ---- */
    .stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1px;
      background: var(--border);
      margin-top: 20px;
      border-radius: 8px;
      overflow: hidden;
    }
    .stat {
      background: var(--bg);
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .stat-val { font-size: 20px; font-weight: 700; color: var(--accent2); }
    .stat-lbl { font-size: 11px; color: var(--muted); }

    /* ---- Progress bar ---- */
    .progress-wrap { margin-top: 16px; }
    .progress-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; display: flex; justify-content: space-between; }
    .progress-bar {
      height: 6px;
      background: var(--border);
      border-radius: 4px;
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      border-radius: 4px;
      transition: width 0.4s ease;
    }

    /* ---- Log panel ---- */
    .log-wrap { position: relative; }

    #log-box {
      padding: 14px 16px;
      height: 480px;
      overflow-y: auto;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12.5px;
      line-height: 1.7;
    }
    #log-box::-webkit-scrollbar { width: 6px; }
    #log-box::-webkit-scrollbar-track { background: var(--surface); }
    #log-box::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

    .log-entry { display: flex; gap: 10px; padding: 2px 0; }
    .log-time { color: #4b5563; min-width: 85px; flex-shrink: 0; }
    .log-level { min-width: 56px; font-weight: 600; flex-shrink: 0; }
    .log-msg { color: var(--text); word-break: break-word; }

    .status-bar {
      padding: 10px 16px;
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      color: var(--muted);
    }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #4b5563; }
    .status-dot.running { background: #22c55e; animation: pulse 1.5s infinite; }
    .status-dot.done    { background: var(--accent2); }
    .status-dot.error   { background: var(--error); }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.4; }
    }

    /* ---- Results panel ---- */
    #results-card { margin-top: 24px; grid-column: 1 / -1; display: none; }

    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 14px;
      padding: 18px;
    }

    .result-item {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 16px;
      transition: border-color 0.2s;
    }
    .result-item:hover { border-color: var(--accent); }

    .result-score {
      font-size: 11px;
      font-weight: 700;
      background: rgba(6,182,212,0.1);
      color: var(--accent2);
      border: 1px solid rgba(6,182,212,0.25);
      border-radius: 20px;
      padding: 2px 10px;
      display: inline-block;
      margin-bottom: 8px;
    }
    .result-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
    .result-url {
      font-size: 11px;
      color: var(--muted);
      text-decoration: none;
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .result-url:hover { color: var(--accent2); }
    .result-snippet { font-size: 12px; color: var(--muted); margin-top: 6px; line-height: 1.5; }

    /* ---- Keywords chips ---- */
    #kw-wrap { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
    .kw-chip {
      font-size: 12px;
      background: rgba(124,58,237,0.12);
      color: #a78bfa;
      border: 1px solid rgba(124,58,237,0.25);
      border-radius: 20px;
      padding: 3px 11px;
    }
  </style>
</head>
<body>

<header>
  <div class="logo">RL</div>
  <div>
    <h1>RAD-ML &mdash; Data Collection Agent</h1>
    <p>Reinforcement Learning &bull; DuckDuckGo &bull; Kaggle &bull; SQLite</p>
  </div>
  <span class="badge">v1.0</span>
</header>

<main>
  <!-- ============ LEFT: Input ============ -->
  <div>
    <div class="card">
      <div class="card-header"><span class="dot"></span>Research Prompt</div>
      <div class="input-panel">
        <label for="prompt">What data do you want to collect?</label>
        <textarea id="prompt" placeholder="e.g. electric vehicle battery datasets machine learning..."></textarea>

        <div class="row">
          <div class="field">
            <label for="episodes">Episodes</label>
            <input type="number" id="episodes" value="5" min="1" max="50"/>
          </div>
          <button class="btn-run" id="run-btn" onclick="runAgent()">&#9654; Run Agent</button>
        </div>

        <div id="kw-wrap"></div>

        <div class="stats">
          <div class="stat"><span class="stat-val" id="s-ep">0</span><span class="stat-lbl">Episodes</span></div>
          <div class="stat"><span class="stat-val" id="s-rew">0.00</span><span class="stat-lbl">Best Reward</span></div>
          <div class="stat"><span class="stat-val" id="s-ddg">0</span><span class="stat-lbl">DDG Saved</span></div>
          <div class="stat"><span class="stat-val" id="s-ver">0</span><span class="stat-lbl">Verified</span></div>
        </div>

        <div class="progress-wrap">
          <div class="progress-label">
            <span>Progress</span>
            <span id="pct">0 / 0</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ============ RIGHT: Live Logs ============ -->
  <div>
    <div class="card log-wrap">
      <div class="card-header"><span class="dot"></span>Live Agent Output</div>
      <div id="log-box"></div>
      <div class="status-bar">
        <div class="status-dot" id="status-dot"></div>
        <span id="status-text">Idle — enter a prompt and click Run Agent</span>
      </div>
    </div>
  </div>

  <!-- ============ FULL WIDTH: Results ============ -->
  <div class="card" id="results-card">
    <div class="card-header"><span class="dot"></span>Top Verified Results (DDG)</div>
    <div class="results-grid" id="results-grid"></div>
  </div>
</main>

<script>
  let evtSource = null;
  let totalEpisodes = 0;
  let doneEpisodes = 0;
  let bestReward = -Infinity;

  function runAgent() {
    const prompt = document.getElementById('prompt').value.trim();
    const episodes = parseInt(document.getElementById('episodes').value) || 5;
    if (!prompt) { alert('Please enter a research prompt.'); return; }

    // Reset UI
    totalEpisodes = episodes;
    doneEpisodes = 0;
    bestReward = -Infinity;
    document.getElementById('log-box').innerHTML = '';
    document.getElementById('kw-wrap').innerHTML = '';
    document.getElementById('results-grid').innerHTML = '';
    document.getElementById('results-card').style.display = 'none';
    document.getElementById('s-ep').textContent = '0';
    document.getElementById('s-rew').textContent = '0.00';
    document.getElementById('s-ddg').textContent = '0';
    document.getElementById('s-ver').textContent = '0';
    setProgress(0, episodes);
    setStatus('running', 'Agent starting…');
    document.getElementById('run-btn').disabled = true;

    if (evtSource) { evtSource.close(); }

    // POST to start, then subscribe to SSE stream
    fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt, episodes})
    }).then(r => r.json()).then(d => {
      if (!d.ok) { setStatus('error', 'Failed to start: ' + d.error); enableBtn(); return; }

      evtSource = new EventSource('/stream');
      evtSource.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        handleMessage(msg);
      };
      evtSource.onerror = () => {
        setStatus('error', 'Stream disconnected.');
        evtSource.close();
        enableBtn();
      };
    }).catch(err => {
      setStatus('error', String(err));
      enableBtn();
    });
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'log':
        appendLog(msg);
        break;
      case 'keywords':
        showKeywords(msg.keywords);
        break;
      case 'episode_done':
        doneEpisodes++;
        if (msg.reward > bestReward) {
          bestReward = msg.reward;
          document.getElementById('s-rew').textContent = bestReward.toFixed(4);
        }
        document.getElementById('s-ep').textContent = doneEpisodes;
        setProgress(doneEpisodes, totalEpisodes);
        break;
      case 'ddg_saved':
        document.getElementById('s-ddg').textContent = msg.total;
        document.getElementById('s-ver').textContent = msg.verified;
        break;
      case 'results':
        showResults(msg.data);
        break;
      case 'done':
        setStatus('done', 'Agent finished — ' + msg.message);
        enableBtn();
        if (evtSource) evtSource.close();
        break;
      case 'error':
        setStatus('error', msg.message);
        enableBtn();
        if (evtSource) evtSource.close();
        break;
    }
  }

  function appendLog({level, colour, message, time}) {
    const box = document.getElementById('log-box');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const t = time ? time.split(' ').pop() : '';
    entry.innerHTML = `
      <span class="log-time">${t}</span>
      <span class="log-level" style="color:${colour}">${level}</span>
      <span class="log-msg">${escHtml(message)}</span>`;
    box.appendChild(entry);
    box.scrollTop = box.scrollHeight;
  }

  function showKeywords(kws) {
    const wrap = document.getElementById('kw-wrap');
    wrap.innerHTML = kws.map(k => `<span class="kw-chip">${escHtml(k)}</span>`).join('');
  }

  function showResults(items) {
    const grid = document.getElementById('results-grid');
    grid.innerHTML = items.map(r => `
      <div class="result-item">
        <span class="result-score">sim ${(r.cosine_sim || 0).toFixed(3)}</span>
        <div class="result-title">${escHtml(r.title || 'Untitled')}</div>
        <a class="result-url" href="${r.url || '#'}" target="_blank">${escHtml(r.url || '')}</a>
        <div class="result-snippet">${escHtml((r.snippet || '').slice(0, 140))}…</div>
      </div>`).join('');
    document.getElementById('results-card').style.display = 'block';
  }

  function setProgress(done, total) {
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    document.getElementById('prog-fill').style.width = pct + '%';
    document.getElementById('pct').textContent = `${done} / ${total}`;
  }

  function setStatus(state, text) {
    document.getElementById('status-dot').className = 'status-dot ' + state;
    document.getElementById('status-text').textContent = text;
  }

  function enableBtn() {
    document.getElementById('run-btn').disabled = false;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Agent runner (runs in a background thread, pushes events to queue)
# ---------------------------------------------------------------------------

_agent_thread: threading.Thread | None = None


def _run_agent_thread(prompt: str, num_episodes: int) -> None:
    """Execute the RAD-ML agent and emit structured events to the SSE queue."""

    def emit(event: dict) -> None:
        _event_queue.put(event)

    try:
        # --- Load config ---
        import yaml  # noqa: PLC0415
        cfg_path = ROOT / "config.yaml"
        if cfg_path.exists():
            with cfg_path.open() as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

        # --- Setup logging to SSE queue ---
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        q_handler = _QueueHandler()
        q_handler.setLevel(logging.INFO)
        q_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        )
        # Remove old QueueHandlers to avoid duplicates
        for h in list(root_logger.handlers):
            if isinstance(h, _QueueHandler):
                root_logger.removeHandler(h)
        root_logger.addHandler(q_handler)

        logger = logging.getLogger("app_ui")

        # --- Import modules ---
        from brain.extractor import KeywordExtractor          # noqa: PLC0415
        from collectors.ddg_search import DDGSearchClient     # noqa: PLC0415
        from collectors.kaggle_client import KaggleClient     # noqa: PLC0415
        from core.agent import RLAgent                        # noqa: PLC0415
        from core.environment import Environment             # noqa: PLC0415
        from core.evolution_engine import EvolutionEngine    # noqa: PLC0415
        from utils.data_cleaner import DataVerifier          # noqa: PLC0415
        from utils.data_store import DataStore               # noqa: PLC0415

        # --- Init components ---
        extractor    = KeywordExtractor(config.get("nlp", {}))
        ddg_client   = DDGSearchClient(config.get("collection", {}))
        kaggle_client = KaggleClient(config)
        verifier     = DataVerifier(config.get("verification", {}))
        agent        = RLAgent(config.get("rl", {}))

        db_path = config.get("storage", {}).get("db_path", "data/rad_ml.db")
        store   = DataStore(db_path)
        session_id = store.start_session(prompt, num_episodes)

        env      = Environment(ddg_client, kaggle_client, verifier, config, store=store)
        evolution = EvolutionEngine(agent, config.get("rl", {}))

        # --- Extract keywords ---
        logger.info("Analysing prompt: '%s'", prompt)
        bundle = extractor.extract(prompt)
        emit({"type": "keywords", "keywords": bundle["primary"]})
        logger.info("Keywords: %s", bundle["primary"])

        action_names = {0: "DuckDuckGo", 1: "Kaggle", 2: "Refine"}
        ddg_total = 0
        ddg_verified = 0

        # --- RL loop ---
        for episode in range(1, num_episodes + 1):
            logger.info("━━━ Episode %d / %d ━━━", episode, num_episodes)
            state = env.reset(bundle)
            ep_reward = 0.0
            done = False

            while not done:
                action = agent.choose_action(state)
                logger.info("→ Action: %s", action_names[action])
                try:
                    next_state, reward, done = env.step(action)
                except ValueError as exc:
                    logger.error("Step error: %s", exc)
                    break

                agent.learn(state, action, reward, next_state)
                ep_reward += reward
                state = next_state

                # Update DDG count if action was DDG
                if action == 0:
                    ddg_total += 1
                    if reward > 0:
                        ddg_verified += 1
                    emit({
                        "type": "ddg_saved",
                        "total": ddg_total,
                        "verified": ddg_verified,
                    })

            evolution.record_episode(ep_reward, episode)
            store.log_episode(
                episode=episode,
                total_reward=ep_reward,
                epsilon_after=agent.epsilon,
                q_states_after=agent.num_states,
            )
            emit({"type": "episode_done", "episode": episode, "reward": ep_reward})

        # --- Finalise ---
        try:
            agent.save_qtable()
        except OSError:
            pass

        store.close_session(agent.epsilon, agent.num_states)

        # --- Top results ---
        top = store.get_top_ddg_results(session_id, limit=10)
        if top:
            emit({"type": "results", "data": top})

        summary = evolution.summary()
        msg = (
            f"Completed {summary.get('total_episodes', 0)} episodes. "
            f"Best avg reward: {summary.get('best_avg_reward', 0):.4f}. "
            f"Q-states: {summary.get('q_states_learned', 0)}."
        )
        emit({"type": "done", "message": msg})

    except Exception as exc:  # noqa: BLE001
        logging.getLogger("app_ui").exception("Agent error")
        emit({"type": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(_HTML)


@app.route("/run", methods=["POST"])
def run():
    global _agent_thread
    data = request.get_json(force=True) or {}
    prompt = str(data.get("prompt", "")).strip()
    try:
        episodes = int(data.get("episodes", 5))
    except (ValueError, TypeError):
        episodes = 5

    if not prompt:
        return jsonify({"ok": False, "error": "Prompt is required."})

    if episodes < 1 or episodes > 50:
        return jsonify({"ok": False, "error": "Episodes must be between 1 and 50."})

    # Clear the queue from any previous run
    while not _event_queue.empty():
        try:
            _event_queue.get_nowait()
        except queue.Empty:
            break

    _agent_thread = threading.Thread(
        target=_run_agent_thread,
        args=(prompt, episodes),
        daemon=True,
    )
    _agent_thread.start()
    return jsonify({"ok": True})


@app.route("/stream")
def stream():
    """SSE endpoint — streams agent events to the browser."""
    def generate():
        while True:
            try:
                event = _event_queue.get(timeout=30)
                yield _sse(event)
                if event.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                # Heartbeat to keep connection alive
                yield "data: {\"type\": \"heartbeat\"}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "agent": "RAD-ML"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RAD-ML — Data Collection Agent UI")
    print("  Open: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
