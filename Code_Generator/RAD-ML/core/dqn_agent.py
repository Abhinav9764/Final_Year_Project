"""
core/dqn_agent.py — Deep Q-Network Reinforcement Learning Agent
==================================================================
The DQN agent decides *how* to tweak the code-generation strategy
between retry attempts, based on:
  - Current attempt number
  - Type/presence of error
  - Cumulative reward so far

State  (6-dim vector):
  [attempt_norm, has_syntax_err, has_runtime_err, has_import_err,
   has_api_err, cumulative_reward_norm]

Actions (4 discrete):
  0 — Use default prompt (baseline)
  1 — Add explicit error context to prompt
  2 — Lower temperature (more deterministic)
  3 — Switch to fallback LLM (DeepSeek → Qwen or vice-versa)

Architecture: 3-layer MLP with experience replay + ε-greedy exploration.
"""

from __future__ import annotations

import random
import logging
from collections import deque
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ── Optional PyTorch import ───────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    log.warning("PyTorch not installed — DQN will use random action selection.")


# ── Neural Network ────────────────────────────────────────────────────────────
if TORCH_AVAILABLE:
    class _QNetwork(nn.Module):
        def __init__(self, state_dim: int, action_dim: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, 128),
                nn.ReLU(),
                nn.Linear(128, 128),
                nn.ReLU(),
                nn.Linear(128, action_dim),
            )

        def forward(self, x):
            return self.net(x)


# ── DQN Agent ─────────────────────────────────────────────────────────────────
class DQNAgent:
    """
    DQN agent that selects generation strategies across retry attempts.

    Args:
        state_dim:  Dimension of the state vector (default 6).
        action_dim: Number of discrete actions (default 4).
        cfg:        Full config dict (reads [dqn] section).
    """

    ACTION_NAMES = {
        0: "default_prompt",
        1: "inject_error_context",
        2: "lower_temperature",
        3: "switch_llm",
    }

    def __init__(self, state_dim: int = 6, action_dim: int = 4, cfg: dict = None):
        cfg = cfg or {}
        dqn_cfg = cfg.get("dqn", {})

        self.state_dim  = state_dim
        self.action_dim = action_dim
        self.gamma       = dqn_cfg.get("gamma", 0.95)
        self.epsilon     = dqn_cfg.get("epsilon", 1.0)
        self.epsilon_min = dqn_cfg.get("epsilon_min", 0.05)
        self.epsilon_dec = dqn_cfg.get("epsilon_decay", 0.90)
        self.lr          = dqn_cfg.get("lr", 0.001)
        self.batch_size  = dqn_cfg.get("batch_size", 32)
        self.memory      = deque(maxlen=dqn_cfg.get("memory_size", 2000))

        if TORCH_AVAILABLE:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.q_net      = _QNetwork(state_dim, action_dim).to(self.device)
            self.target_net = _QNetwork(state_dim, action_dim).to(self.device)
            self.target_net.load_state_dict(self.q_net.state_dict())
            self.optimizer  = optim.Adam(self.q_net.parameters(), lr=self.lr)
            self.loss_fn    = nn.MSELoss()
            log.info("DQN initialised on %s", self.device)
        else:
            log.info("DQN running in random-action mode (no PyTorch).")

    # ── State Encoding ────────────────────────────────────────────────────────
    def encode_state(
        self,
        attempt: int,
        error: Optional[str],
        cumulative_reward: float,
        max_attempts: int = 5,
    ) -> np.ndarray:
        """Encode environment info into a fixed-length float32 vector."""
        err_lower = (error or "").lower()
        return np.array([
            attempt / max(max_attempts, 1),            # normalised attempt#
            float("syntaxerror"  in err_lower or "syntax" in err_lower),
            float("runtimeerror" in err_lower or "traceback" in err_lower),
            float("importerror"  in err_lower or "modulenotfounderror" in err_lower),
            float("api"          in err_lower or "timeout" in err_lower or "rate" in err_lower),
            min(max(cumulative_reward / 10.0, -1.0), 1.0),   # clip-normalised reward
        ], dtype=np.float32)

    # ── Action Selection ──────────────────────────────────────────────────────
    def choose_action(self, state: np.ndarray) -> int:
        """ε-greedy policy."""
        if not TORCH_AVAILABLE or random.random() < self.epsilon:
            action = random.randint(0, self.action_dim - 1)
            log.debug("DQN explore → action %d (%s)", action, self.ACTION_NAMES[action])
            return action

        with torch.no_grad():
            s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_vals = self.q_net(s)
            action = int(q_vals.argmax().item())
        log.debug("DQN exploit → action %d (%s)", action, self.ACTION_NAMES[action])
        return action

    # ── Memory + Learning ─────────────────────────────────────────────────────
    def update(
        self,
        state:      np.ndarray,
        action:     int,
        reward:     float,
        next_state: np.ndarray,
        done:       bool = False,
    ) -> None:
        """Store transition and trigger a learning step."""
        self.memory.append((state, action, reward, next_state, done))
        self._decay_epsilon()

        if len(self.memory) >= self.batch_size and TORCH_AVAILABLE:
            self._learn()

    def _learn(self) -> None:
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        states      = torch.FloatTensor(np.array(states)).to(self.device)
        actions     = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        rewards     = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones       = torch.FloatTensor(dones).to(self.device)

        current_q   = self.q_net(states).gather(1, actions).squeeze(1)
        with torch.no_grad():
            max_next_q  = self.target_net(next_states).max(1)[0]
            target_q    = rewards + self.gamma * max_next_q * (1 - dones)

        loss = self.loss_fn(current_q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        log.debug("DQN training step — loss=%.5f", loss.item())

    def _decay_epsilon(self) -> None:
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_dec)

    def sync_target(self) -> None:
        """Periodically sync target network weights."""
        if TORCH_AVAILABLE:
            self.target_net.load_state_dict(self.q_net.state_dict())
