"""
backend/auth_db.py
===================
SQLite user store — handles registration, login, and user lookups.
Passwords are hashed with bcrypt (never stored in plain text).

Schema
------
users(id INTEGER PK, username TEXT UNIQUE, email TEXT UNIQUE,
      password_hash TEXT, google_id TEXT, avatar_url TEXT,
      created_at REAL)
"""
from __future__ import annotations
import sqlite3
import time
import logging
from pathlib import Path

import bcrypt

logger = logging.getLogger(__name__)
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent


class AuthDB:
    def __init__(self, db_path: str = "data/users.db"):
        self._path = self._resolve_path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Auth DB path resolved to %s", self._path)
        self._init_schema()

    @staticmethod
    def _resolve_path(db_path: str) -> Path:
        path = Path(db_path).expanduser()
        if path.is_absolute():
            return path

        # Prefer the backend-local data directory so auth always uses the
        # same SQLite file regardless of the process working directory.
        backend_relative = (_HERE / path).resolve()
        if backend_relative.parent.exists() or backend_relative.exists():
            return backend_relative

        project_relative = (_PROJECT_ROOT / path).resolve()
        if project_relative.exists():
            return project_relative

        return backend_relative

    # ── schema ────────────────────────────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                email        TEXT    UNIQUE COLLATE NOCASE,
                password_hash TEXT,
                google_id    TEXT    UNIQUE,
                avatar_url   TEXT,
                created_at   REAL    NOT NULL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_users_google   ON users(google_id);
            """)

    # ── registration ──────────────────────────────────────────────────────────
    def register(self, username: str, password: str,
                 email: str = "") -> dict:
        """
        Create a new user. Returns user dict or raises ValueError.
        """
        username = username.strip()
        if not username or len(username) < 2:
            raise ValueError("Username must be at least 2 characters.")
        if len(username) > 32:
            raise ValueError("Username must be 32 characters or fewer.")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            with self._conn() as c:
                cur = c.execute(
                    "INSERT INTO users (username, email, password_hash, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (username, email.strip() or None, pw_hash, time.time()),
                )
                user_id = cur.lastrowid
            logger.info("Registered user: %s (id=%s)", username, user_id)
            return {"id": user_id, "username": username, "email": email}
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' is already taken.")

    # ── login ─────────────────────────────────────────────────────────────────
    def login(self, username: str, password: str) -> dict | None:
        """
        Verify credentials. Returns user dict on success, None on failure.
        """
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
                (username.strip(),),
            ).fetchone()

        if row is None:
            return None
        if not row["password_hash"]:
            return None   # Google-only account
        try:
            if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                return None
        except ValueError as exc:
            logger.warning(
                "Skipping login for user '%s' because stored password hash is invalid: %s",
                username.strip(),
                exc,
            )
            return None
        return dict(row)

    # ── google OAuth ──────────────────────────────────────────────────────────
    def upsert_google_user(self, google_id: str, email: str,
                           name: str, avatar_url: str = "") -> dict:
        """Create or update a Google-authenticated user."""
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM users WHERE google_id = ?", (google_id,)
            ).fetchone()

            if row:
                c.execute(
                    "UPDATE users SET avatar_url=?, email=? WHERE google_id=?",
                    (avatar_url, email, google_id),
                )
                return dict(row)

            # New Google user — derive unique username from email
            base = email.split("@")[0].replace(".", "_")
            username = base
            suffix = 2
            while c.execute(
                "SELECT 1 FROM users WHERE username=? COLLATE NOCASE",
                (username,)
            ).fetchone():
                username = f"{base}{suffix}"
                suffix += 1

            gcur = c.execute(
                "INSERT INTO users (username, email, google_id, avatar_url, created_at)"
                " VALUES (?,?,?,?,?)",
                (username, email, google_id, avatar_url, time.time()),
            )
            return {
                "id":       gcur.lastrowid,
                "username": username,
                "email":    email,
                "google_id": google_id,
                "avatar_url": avatar_url,
            }

    # ── lookup ────────────────────────────────────────────────────────────────
    def get_by_id(self, user_id: int) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT id, username, email, avatar_url, created_at"
                " FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None
