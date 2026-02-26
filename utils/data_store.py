"""
utils/data_store.py
====================
SQLite-backed persistent data store for the RAD-ML agent.

All collected results, verification reports, and episode rewards are
written here so no data is ever lost between sessions.

Schema
------
  sessions      — one row per agent run (timestamp, prompt, episodes)
  ddg_results   — each DuckDuckGo result with verification outcome
  kaggle_results— each Kaggle dataset entry found
  episode_log   — per-episode reward totals
  step_log      — per-step action/reward/state for full reproducibility
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL — schema definition
# ---------------------------------------------------------------------------

_CREATE_TABLES = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT    NOT NULL,
    prompt      TEXT    NOT NULL,
    num_episodes INTEGER NOT NULL,
    final_epsilon REAL,
    q_states    INTEGER
);

CREATE TABLE IF NOT EXISTS ddg_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    episode         INTEGER NOT NULL,
    step            INTEGER NOT NULL,
    query           TEXT    NOT NULL,
    title           TEXT,
    url             TEXT,
    snippet         TEXT,
    cleaned_text    TEXT,
    verified        INTEGER NOT NULL DEFAULT 0,   -- 0=fail, 1=pass
    cosine_sim      REAL,
    keyword_cov     REAL,
    text_length     INTEGER,
    collected_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS kaggle_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    episode         INTEGER NOT NULL,
    step            INTEGER NOT NULL,
    ref             TEXT    NOT NULL,
    title           TEXT,
    size_bytes      INTEGER,
    tags            TEXT,   -- JSON array string
    url             TEXT,
    verified        INTEGER NOT NULL DEFAULT 0,
    cosine_sim      REAL,
    keyword_cov     REAL,
    collected_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS episode_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    episode         INTEGER NOT NULL,
    total_reward    REAL    NOT NULL,
    epsilon_after   REAL,
    q_states_after  INTEGER,
    completed_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS step_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    episode         INTEGER NOT NULL,
    step            INTEGER NOT NULL,
    state_hash      TEXT,
    action          INTEGER NOT NULL,   -- 0=DDG, 1=Kaggle, 2=Refine
    reward          REAL    NOT NULL,
    next_state_hash TEXT,
    keywords        TEXT,               -- JSON array string
    done            INTEGER NOT NULL DEFAULT 0
);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# DataStore
# ---------------------------------------------------------------------------

class DataStore:
    """
    SQLite-backed store for all RAD-ML collected data.

    Parameters
    ----------
    db_path : str | Path
        Path to the SQLite database file.
        Created automatically if it does not exist.

    Raises
    ------
    OSError
        If the parent directory cannot be created.
    sqlite3.DatabaseError
        On unrecoverable database errors.
    """

    ACTION_NAMES = {0: "ddg", 1: "kaggle", 2: "refine"}

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id: Optional[int] = None
        self._init_db()
        logger.info("DataStore ready → %s", self._db_path)

    # ------------------------------------------------------------------
    # Internal connection context manager
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield an auto-committing database connection."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except sqlite3.DatabaseError as exc:
            conn.rollback()
            logger.error("Database error: %s", exc)
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables if they don't already exist."""
        try:
            with self._connect() as conn:
                conn.executescript(_CREATE_TABLES)
            logger.debug("Database schema initialised.")
        except sqlite3.DatabaseError as exc:
            raise sqlite3.DatabaseError(
                f"Failed to initialise database at '{self._db_path}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_session(self, prompt: str, num_episodes: int) -> int:
        """
        Register a new agent run and return its session ID.

        Parameters
        ----------
        prompt : str
            The user's research prompt for this run.
        num_episodes : int
            Number of planned episodes.

        Returns
        -------
        int
            The new session's primary key.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sessions (started_at, prompt, num_episodes)
                VALUES (?, ?, ?)
                """,
                (_now(), prompt, num_episodes),
            )
            self._session_id = cur.lastrowid

        logger.info("Session %d started (prompt: '%s…')", self._session_id, prompt[:40])
        return self._session_id  # type: ignore[return-value]

    def close_session(self, final_epsilon: float, q_states: int) -> None:
        """Update the session row with final agent statistics."""
        if self._session_id is None:
            logger.warning("close_session called without an active session.")
            return
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET final_epsilon = ?, q_states = ?
                WHERE id = ?
                """,
                (final_epsilon, q_states, self._session_id),
            )
        logger.info(
            "Session %d closed (ε=%.4f, Q-states=%d).",
            self._session_id,
            final_epsilon,
            q_states,
        )

    # ------------------------------------------------------------------
    # DDG results
    # ------------------------------------------------------------------

    def save_ddg_results(
        self,
        episode: int,
        step: int,
        query: str,
        results: list[dict[str, Any]],
        verification_report: Optional[dict] = None,
        cleaned_text: str = "",
    ) -> None:
        """
        Persist all DuckDuckGo results for a single search action.

        Parameters
        ----------
        episode, step : int
            Current episode and step number.
        query : str
            Search query used.
        results : list[dict]
            Raw result dicts from `DDGSearchClient.search()`.
        verification_report : dict | None
            Output of `DataVerifier.verify()`, if run.
        cleaned_text : str
            Combined cleaned text from all results.
        """
        if self._session_id is None:
            raise RuntimeError("Call start_session() before saving results.")

        verified = int(
            (verification_report or {}).get("overall_passed", False)
        )
        cosine_sim = float(
            ((verification_report or {}).get("cosine_similarity") or {}).get("value", 0.0)
        )
        kw_cov = float(
            ((verification_report or {}).get("keyword_coverage") or {}).get("value", 0.0)
        )
        text_len = len(cleaned_text)

        rows = []
        for r in results:
            rows.append((
                self._session_id,
                episode,
                step,
                query,
                r.get("title", ""),
                r.get("url", ""),
                r.get("snippet", ""),
                cleaned_text,
                verified,
                cosine_sim,
                kw_cov,
                text_len,
                _now(),
            ))

        if not rows:
            # Save a placeholder so the step is still recorded
            rows.append((
                self._session_id, episode, step, query,
                "", "", "", cleaned_text, verified,
                cosine_sim, kw_cov, text_len, _now(),
            ))

        try:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO ddg_results
                        (session_id, episode, step, query, title, url,
                         snippet, cleaned_text, verified, cosine_sim,
                         keyword_cov, text_length, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            logger.debug(
                "Saved %d DDG result(s) — ep=%d step=%d verified=%s",
                len(rows), episode, step, bool(verified),
            )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to save DDG results: %s", exc)

    # ------------------------------------------------------------------
    # Kaggle results
    # ------------------------------------------------------------------

    def save_kaggle_results(
        self,
        episode: int,
        step: int,
        results: list[dict[str, Any]],
        verification_report: Optional[dict] = None,
    ) -> None:
        """
        Persist Kaggle dataset search results.

        Parameters
        ----------
        episode, step : int
        results : list[dict]
            Output of `KaggleClient.search_datasets()`.
        verification_report : dict | None
        """
        if self._session_id is None:
            raise RuntimeError("Call start_session() before saving results.")

        verified = int(
            (verification_report or {}).get("overall_passed", False)
        )
        cosine_sim = float(
            ((verification_report or {}).get("cosine_similarity") or {}).get("value", 0.0)
        )
        kw_cov = float(
            ((verification_report or {}).get("keyword_coverage") or {}).get("value", 0.0)
        )

        rows = []
        for ds in results:
            rows.append((
                self._session_id,
                episode,
                step,
                ds.get("ref", ""),
                ds.get("title", ""),
                ds.get("size", 0),
                json.dumps(ds.get("tags", [])),
                ds.get("url", ""),
                verified,
                cosine_sim,
                kw_cov,
                _now(),
            ))

        if not rows:
            return

        try:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO kaggle_results
                        (session_id, episode, step, ref, title, size_bytes,
                         tags, url, verified, cosine_sim, keyword_cov, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            logger.debug(
                "Saved %d Kaggle dataset(s) — ep=%d step=%d.",
                len(rows), episode, step,
            )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to save Kaggle results: %s", exc)

    # ------------------------------------------------------------------
    # Episode & step logs
    # ------------------------------------------------------------------

    def log_episode(
        self,
        episode: int,
        total_reward: float,
        epsilon_after: float,
        q_states_after: int,
    ) -> None:
        """Record end-of-episode summary."""
        if self._session_id is None:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO episode_log
                        (session_id, episode, total_reward, epsilon_after,
                         q_states_after, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (self._session_id, episode, total_reward,
                     epsilon_after, q_states_after, _now()),
                )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to log episode: %s", exc)

    def log_step(
        self,
        episode: int,
        step: int,
        state: str,
        action: int,
        reward: float,
        next_state: str,
        keywords: list[str],
        done: bool,
    ) -> None:
        """Record a single (s, a, r, s') transition."""
        if self._session_id is None:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO step_log
                        (session_id, episode, step, state_hash, action,
                         reward, next_state_hash, keywords, done)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self._session_id, episode, step, state, action,
                        reward, next_state, json.dumps(keywords), int(done),
                    ),
                )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to log step: %s", exc)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_top_ddg_results(
        self, session_id: Optional[int] = None, limit: int = 10
    ) -> list[dict]:
        """
        Return the top DDG results by cosine similarity score.

        Parameters
        ----------
        session_id : int | None
            Filter to a specific session; None = all sessions.
        limit : int
            Maximum rows to return.
        """
        sid = session_id or self._session_id
        query = """
            SELECT title, url, snippet, cosine_sim, keyword_cov,
                   verified, episode, step
            FROM ddg_results
            WHERE (:sid IS NULL OR session_id = :sid)
              AND verified = 1
            ORDER BY cosine_sim DESC
            LIMIT :limit
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(query, {"sid": sid, "limit": limit}).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.DatabaseError as exc:
            logger.error("Query failed: %s", exc)
            return []

    def get_session_summary(self, session_id: Optional[int] = None) -> dict:
        """Return a summary dict for a session."""
        sid = session_id or self._session_id
        result: dict[str, Any] = {"session_id": sid}
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE id = ?", (sid,)
                ).fetchone()
                if row:
                    result.update(dict(row))

                stats = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS total_ddg,
                        SUM(verified) AS verified_ddg,
                        AVG(cosine_sim) AS avg_sim
                    FROM ddg_results WHERE session_id = ?
                    """,
                    (sid,),
                ).fetchone()
                if stats:
                    result["ddg_total"] = stats["total_ddg"]
                    result["ddg_verified"] = stats["verified_ddg"]
                    result["ddg_avg_similarity"] = round(stats["avg_sim"] or 0.0, 4)

                k_stats = conn.execute(
                    "SELECT COUNT(*) AS total FROM kaggle_results WHERE session_id = ?",
                    (sid,),
                ).fetchone()
                if k_stats:
                    result["kaggle_total"] = k_stats["total"]

        except sqlite3.DatabaseError as exc:
            logger.error("Session summary failed: %s", exc)
        return result
