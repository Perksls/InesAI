"""InesBot Authentication - Sessions, Users, Security"""
import os
import sqlite3
import secrets
import hashlib
import time
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta

from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse

logger = logging.getLogger("inesbot.auth")

# ── Config ──────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("INESBOT_SECRET", secrets.token_hex(32))
SESSION_COOKIE = "inesbot_session"
SESSION_EXPIRE_HOURS = 24 * 7   # 1 semana
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300      # 5 minutos


# ── Paths (resolvidos relativamente a este ficheiro) ─────────────────────
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "chats.db"


# ── In-memory rate limiter ───────────────────────────────────────────────
# { ip: {"count": int, "first_attempt": float, "locked_until": float} }
_login_attempts: Dict[str, dict] = {}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_rate_limited(ip: str) -> tuple[bool, int]:
    """Returns (is_blocked, seconds_remaining)"""
    now = time.time()
    entry = _login_attempts.get(ip)
    if not entry:
        return False, 0
    if entry.get("locked_until", 0) > now:
        return True, int(entry["locked_until"] - now)
    # Reset if window expired (10 min)
    if now - entry.get("first_attempt", 0) > 600:
        _login_attempts.pop(ip, None)
        return False, 0
    return False, 0


def record_login_attempt(ip: str, success: bool):
    now = time.time()
    if success:
        _login_attempts.pop(ip, None)
        return
    entry = _login_attempts.setdefault(ip, {"count": 0, "first_attempt": now})
    entry["count"] += 1
    if entry["count"] >= LOGIN_MAX_ATTEMPTS:
        entry["locked_until"] = now + LOGIN_LOCKOUT_SECONDS
        logger.warning(f"IP {ip} bloqueado por {LOGIN_LOCKOUT_SECONDS}s após {entry['count']} tentativas falhadas")


# ── Password utils ───────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """PBKDF2-SHA256, sem dependências extra"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, algo, iterations, salt, dk_hex = stored.split(":")
        dk = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), int(iterations))
        return secrets.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── Session token ────────────────────────────────────────────────────────
def _sign(token: str) -> str:
    import hmac
    sig = hmac.new(SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def _verify_signed(signed: str) -> Optional[str]:
    import hmac
    try:
        token, sig = signed.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
        if secrets.compare_digest(sig, expected):
            return token
    except Exception:
        pass
    return None


# ── DB helpers ───────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    """Create users and sessions tables (call once at startup)"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Garantir que sessions e messages têm coluna user_id
    try:
        cur.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        logger.info("Coluna user_id adicionada à tabela sessions")
    except sqlite3.OperationalError:
        pass  # já existe

    conn.commit()
    conn.close()
    logger.info("Auth DB inicializado")


# ── User management ──────────────────────────────────────────────────────
def create_user(username: str, password: str, is_admin: bool = False) -> int:
    conn = _db()
    cur = conn.cursor()
    hashed = hash_password(password)
    cur.execute(
        "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
        (username, hashed, 1 if is_admin else 0)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Utilizador criado: {username} (admin={is_admin})")
    return user_id


def get_user_by_username(username: str) -> Optional[dict]:
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_users() -> list:
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user(user_id: int):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def change_password(user_id: int, new_password: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(new_password), user_id))
    conn.commit()
    conn.close()


# ── Session management ───────────────────────────────────────────────────
def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)
    conn = _db()
    conn.execute(
        "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires.isoformat())
    )
    conn.commit()
    conn.close()
    return _sign(token)


def get_session_user(signed_token: str) -> Optional[dict]:
    token = _verify_signed(signed_token)
    if not token:
        return None
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, expires_at FROM user_sessions WHERE token = ?", (token,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        invalidate_session(signed_token)
        return None
    return get_user_by_id(row["user_id"])


def invalidate_session(signed_token: str):
    token = _verify_signed(signed_token)
    if not token:
        return
    conn = _db()
    conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def cleanup_expired_sessions():
    conn = _db()
    conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
    conn.commit()
    conn.close()


# ── FastAPI helpers ──────────────────────────────────────────────────────
def get_current_user(request: Request) -> Optional[dict]:
    """Extract user from cookie — returns None if not authenticated"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return get_session_user(token)


def require_auth(request: Request) -> dict:
    """Use as a dependency — raises 401 if not logged in"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return user


def require_auth_ws(request: Request) -> Optional[dict]:
    """For WebSocket — returns None instead of raising (WS handles differently)"""
    return get_current_user(request)


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=False,       # Mudar para True quando tiveres HTTPS
        samesite="lax",
        max_age=SESSION_EXPIRE_HOURS * 3600,
        path="/"
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, path="/")


# ── Login attempt tracking ───────────────────────────────────────────────
def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user:
        return None
    if verify_password(password, user["password"]):
        return user
    return None
