"""
generator/templates/base_css.py — Base CSS Template (dark glassmorphism)
=========================================================================
Modern dark-mode CSS with glassmorphism, smooth animations, and responsiveness.
Used as both the offline fallback and the style guide sent to the LLM.
"""

BASE_CSS = """
/* ── Reset & Base ──────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:         #0d0f1a;
  --surface:    rgba(255,255,255,0.05);
  --surface2:   rgba(255,255,255,0.09);
  --border:     rgba(255,255,255,0.10);
  --accent:     #7c6af7;
  --accent2:    #3ecfff;
  --text:       #e8eaf0;
  --muted:      #8a8fa8;
  --error:      #ff5e72;
  --success:    #3ecfff;
  --radius:     14px;
  --shadow:     0 8px 40px rgba(0,0,0,0.45);
  --glow-accent: 0 0 20px rgba(124,106,247,0.45);
  --glow-blue:   0 0 20px rgba(62,207,255,0.45);
  --transition:  all 0.25s ease;
}

html, body {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', 'Outfit', system-ui, sans-serif;
  line-height: 1.6;
}

/* ── App Container ───────────────────────────────────────────────────────── */
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 40px;
  max-width: 860px;
  margin: 0 auto;
}

/* ── Header ─────────────────────────────────────────────────────────────── */
.app-header {
  text-align: center;
  margin-bottom: 32px;
}

.app-header h1 {
  font-size: clamp(2rem, 5vw, 3rem);
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.accent { color: var(--accent2); }

.subtitle {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 4px;
  letter-spacing: 0.5px;
}

/* Animated pulse logo dot */
.logo-pulse {
  width: 14px; height: 14px;
  background: var(--accent);
  border-radius: 50%;
  margin: 0 auto 10px;
  box-shadow: var(--glow-accent);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%       { transform: scale(1.5); opacity: 0.6; }
}

/* ── Glass Card ──────────────────────────────────────────────────────────── */
.glass-card {
  background: var(--surface);
  border: 1px solid var(--border);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 28px;
  width: 100%;
}

/* ── Chat Window ─────────────────────────────────────────────────────────── */
.chat-window {
  width: 100%;
  height: 420px;
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scroll-behavior: smooth;
  backdrop-filter: blur(12px);
}

.chat-window::-webkit-scrollbar { width: 6px; }
.chat-window::-webkit-scrollbar-track { background: transparent; }
.chat-window::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 3px; }

/* ── Messages ────────────────────────────────────────────────────────────── */
.message {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  animation: fadeUp 0.3s ease;
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.bot-message  { justify-content: flex-start; }
.user-message { justify-content: flex-end; }
.error-message { justify-content: center; }

.avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
}
.bot-avatar  { background: linear-gradient(135deg, var(--accent), #5b4bd1); }
.user-avatar { background: linear-gradient(135deg, var(--accent2), #28a0c2); }

.bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 0.93rem;
  line-height: 1.55;
  word-break: break-word;
}
.bot-message  .bubble { background: var(--surface2); border-bottom-left-radius: 4px; }
.user-message .bubble {
  background: linear-gradient(135deg, var(--accent), #5b4bd1);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.error-bubble { background: rgba(255,94,114,0.15); color: var(--error); border-radius: 10px; }

/* ── Input Area ──────────────────────────────────────────────────────────── */
.input-area {
  display: flex;
  gap: 10px;
  width: 100%;
  margin-top: 14px;
}

.chat-input {
  flex: 1;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 18px;
  color: var(--text);
  font-size: 0.95rem;
  outline: none;
  transition: var(--transition);
}
.chat-input:focus {
  border-color: var(--accent);
  box-shadow: var(--glow-accent);
}

.send-btn {
  background: linear-gradient(135deg, var(--accent), #5b4bd1);
  border: none;
  border-radius: 12px;
  padding: 12px 24px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.95rem;
  transition: var(--transition);
  display: flex; align-items: center; gap: 8px;
}
.send-btn:hover { filter: brightness(1.15); transform: translateY(-1px); }
.send-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

/* ── Prediction Form ─────────────────────────────────────────────────────── */
.prediction-form {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  backdrop-filter: blur(16px);
  border-radius: var(--radius);
  padding: 32px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
  box-shadow: var(--shadow);
}

.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.field-group input {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 14px;
  color: var(--text);
  font-size: 0.92rem;
  outline: none;
  transition: var(--transition);
}
.field-group input:focus {
  border-color: var(--accent2);
  box-shadow: var(--glow-blue);
}

.predict-btn {
  grid-column: 1 / -1;
  background: linear-gradient(135deg, var(--accent2), #28a0c2);
  border: none;
  border-radius: 12px;
  padding: 14px 30px;
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  letter-spacing: 0.3px;
  transition: var(--transition);
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.predict-btn:hover { filter: brightness(1.12); transform: translateY(-2px); box-shadow: var(--glow-blue); }
.predict-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

/* ── Result Card ─────────────────────────────────────────────────────────── */
.result-card {
  margin-top: 24px;
  width: 100%;
  background: var(--surface);
  border: 1px solid rgba(62,207,255,0.35);
  border-radius: var(--radius);
  padding: 28px;
  text-align: center;
  box-shadow: var(--glow-blue);
  animation: fadeUp 0.4s ease;
}
.result-label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--muted);
  margin-bottom: 8px;
}
.result-value {
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: 800;
  background: linear-gradient(135deg, var(--accent2), var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Metrics + badges */
.chip-row {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.chip {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 0.82rem;
  color: var(--text);
}
.metrics-card {
  margin-top: 18px;
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px;
  box-shadow: var(--shadow);
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-top: 10px;
}
.metric-item {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.metric-key {
  font-size: 0.78rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
.metric-val {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
}

/* ── Error Banner ────────────────────────────────────────────────────────── */
.error-banner {
  margin-top: 16px;
  width: 100%;
  background: rgba(255,94,114,0.12);
  border: 1px solid rgba(255,94,114,0.3);
  border-radius: 10px;
  padding: 12px 16px;
  color: var(--error);
  font-size: 0.9rem;
  text-align: center;
}

/* ── Spinner ─────────────────────────────────────────────────────────────── */
.spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Utility ─────────────────────────────────────────────────────────────── */
.hidden { display: none !important; }

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 480px) {
  .prediction-form { grid-template-columns: 1fr; }
  .bubble { max-width: 90%; }
  .chip-row { flex-direction: column; }
}
"""
