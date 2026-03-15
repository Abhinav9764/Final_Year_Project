"""
generator/templates/base_html.py
================================
Base HTML templates for both app modes.
Used as offline fallbacks and as style guides for the LLM.
"""

# ---------------------------------------------------------------------------
# CHATBOT HTML
# ---------------------------------------------------------------------------
HTML_CHATBOT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RAD-ML Chatbot</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  <div class="app-container">
    <header class="app-header">
      <div class="logo-pulse"></div>
      <h1>RAD-ML <span class="accent">Chatbot</span></h1>
      <p class="subtitle">RAG + SLM Assistant</p>
    </header>

    <div class="chip-row">
      <span class="chip" id="algoChip">Algorithm: Loading...</span>
      <span class="chip" id="respChip">Responses: 0</span>
      <span class="chip" id="latencyChip">Avg Latency: 0 ms</span>
    </div>

    <div class="chat-window" id="chatWindow">
      <div class="message bot-message">
        <div class="avatar bot-avatar">BOT</div>
        <div class="bubble">Ask a question from your indexed knowledge base.</div>
      </div>
    </div>

    <div class="input-area">
      <input type="text" id="userInput" class="chat-input" placeholder="Type your question..." autocomplete="off">
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">
        <span id="btnText">Send</span>
        <span id="spinner" class="spinner hidden"></span>
      </button>
    </div>
  </div>

  <script>
    const chatWindow = document.getElementById("chatWindow");
    const userInput = document.getElementById("userInput");
    const sendBtn = document.getElementById("sendBtn");

    userInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendMessage();
    });

    async function refreshMetrics() {
      try {
        const resp = await fetch("/metrics");
        const data = await resp.json();
        const metrics = data.metrics || {};
        document.getElementById("algoChip").textContent = `Algorithm: ${data.algorithm || "N/A"}`;
        document.getElementById("respChip").textContent = `Responses: ${metrics.response_count ?? 0}`;
        document.getElementById("latencyChip").textContent = `Avg Latency: ${metrics.avg_latency_ms ?? 0} ms`;
      } catch (_) {}
    }

    function appendMessage(text, role) {
      const div = document.createElement("div");
      div.className = `message ${role}-message`;
      if (role === "bot") {
        div.innerHTML = `<div class="avatar bot-avatar">BOT</div><div class="bubble">${escapeHtml(text)}</div>`;
      } else {
        div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div><div class="avatar user-avatar">YOU</div>`;
      }
      chatWindow.appendChild(div);
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function appendError(text) {
      const div = document.createElement("div");
      div.className = "message error-message";
      div.innerHTML = `<div class="bubble error-bubble">${escapeHtml(text)}</div>`;
      chatWindow.appendChild(div);
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function setLoading(isLoading) {
      sendBtn.disabled = isLoading;
      document.getElementById("btnText").textContent = isLoading ? "Sending..." : "Send";
      document.getElementById("spinner").classList.toggle("hidden", !isLoading);
    }

    async function sendMessage() {
      const msg = userInput.value.trim();
      if (!msg) return;

      appendMessage(msg, "user");
      userInput.value = "";
      setLoading(true);

      try {
        const resp = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: msg }),
        });
        const data = await resp.json();
        if (data.error) appendError(data.error);
        else appendMessage(data.response || "", "bot");
      } catch (err) {
        appendError(String(err));
      } finally {
        setLoading(false);
        refreshMetrics();
      }
    }

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    refreshMetrics();
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# ML PREDICTION HTML
# ---------------------------------------------------------------------------
HTML_ML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RAD-ML Predictor</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  <div class="app-container">
    <header class="app-header">
      <div class="logo-pulse"></div>
      <h1>RAD-ML <span class="accent">Predictor</span></h1>
      <p class="subtitle">Interactive model inference</p>
    </header>

    <div class="chip-row">
      <span class="chip" id="algorithmBadge">Algorithm: Loading...</span>
    </div>

    <form class="prediction-form" id="predForm" onsubmit="submitPrediction(event)">
      {% for feature in features %}
      <div class="field-group">
        <label for="{{ feature }}">{{ feature | replace('_', ' ') | title }}</label>
        <input type="text" id="{{ feature }}" name="{{ feature }}" placeholder="Enter {{ feature }}" required>
      </div>
      {% endfor %}
      <button class="predict-btn" type="submit" id="predictBtn">
        <span id="btnText">Predict</span>
        <span id="spinner" class="spinner hidden"></span>
      </button>
    </form>

    <div class="result-card hidden" id="resultCard">
      <p class="result-label">Prediction Result</p>
      <p class="result-value" id="resultValue">-</p>
    </div>

    <div class="metrics-card" id="metricsCard">
      <p class="result-label">Model Metrics</p>
      <div id="metricsGrid" class="metrics-grid"></div>
    </div>

    <div class="error-banner hidden" id="errorBanner"></div>
  </div>

  <script>
    async function loadMetrics() {
      try {
        const resp = await fetch("/metrics");
        const data = await resp.json();
        document.getElementById("algorithmBadge").textContent = `Algorithm: ${data.algorithm || "N/A"}`;
        const metrics = data.metrics || {};
        const grid = document.getElementById("metricsGrid");
        grid.innerHTML = "";
        Object.keys(metrics).forEach((k) => {
          const item = document.createElement("div");
          item.className = "metric-item";
          item.innerHTML = `<span class="metric-key">${k}</span><span class="metric-val">${metrics[k]}</span>`;
          grid.appendChild(item);
        });
      } catch (err) {
        showError("Unable to load model metrics: " + err);
      }
    }

    async function submitPrediction(e) {
      e.preventDefault();
      setLoading(true);
      hideError();
      document.getElementById("resultCard").classList.add("hidden");

      const form = new FormData(document.getElementById("predForm"));
      try {
        const resp = await fetch("/predict", { method: "POST", body: form });
        const data = await resp.json();
        if (data.error) {
          showError(data.error);
          return;
        }
        showResult(data.prediction);
      } catch (err) {
        showError(String(err));
      } finally {
        setLoading(false);
      }
    }

    function showResult(val) {
      document.getElementById("resultValue").textContent = val;
      document.getElementById("resultCard").classList.remove("hidden");
    }

    function showError(msg) {
      const el = document.getElementById("errorBanner");
      el.textContent = msg;
      el.classList.remove("hidden");
    }

    function hideError() {
      document.getElementById("errorBanner").classList.add("hidden");
    }

    function setLoading(isLoading) {
      const btn = document.getElementById("predictBtn");
      btn.disabled = isLoading;
      document.getElementById("btnText").textContent = isLoading ? "Processing..." : "Predict";
      document.getElementById("spinner").classList.toggle("hidden", !isLoading);
    }

    loadMetrics();
  </script>
</body>
</html>
"""
