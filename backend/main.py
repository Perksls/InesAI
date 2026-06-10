"""InesBot WebSocket Backend - Multi-Provider with Dynamic Fallback"""
import asyncio
import json
import sqlite3
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path

# Adicionar pasta backend ao path para imports funcionarem
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from models import config
from search import web_search
from auth import (
    init_auth_db, get_current_user, require_auth, authenticate_user,
    create_session, invalidate_session, set_session_cookie, clear_session_cookie,
    is_rate_limited, record_login_attempt, cleanup_expired_sessions,
    SESSION_COOKIE
)
from mcp import (
    build_context,
    get_tool_definitions,
    handle_tool_call,
    extract_tool_calls,
    is_tools_supported,
)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "chats.db"
FRONTEND_DIR = BASE_DIR / "frontend"
LOGS_DIR = BASE_DIR / "logs"

# Criar diretorios necessarios
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(str(LOGS_DIR / "backend.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("inesbot")

# Database lock
DB_LOCK = asyncio.Lock()

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT DEFAULT 'Novo Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            model TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Base de dados inicializada")

def get_db():
    """Get database connection"""
    return sqlite3.connect(str(DB_PATH))

def save_message(session_id: int, role: str, content: str, model: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content, model) VALUES (?, ?, ?, ?)",
        (session_id, role, content, model)
    )
    conn.commit()
    conn.close()

def get_messages(session_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, model FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "model": r[2]} for r in rows]

def get_sessions(user_id: int) -> List[Dict[str, Any]]:
    """Get sessions for a specific user only"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, created_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]

def create_chat_session(user_id: int, name: str = "Novo Chat") -> int:
    """Create new session owned by user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (user_id, name) VALUES (?, ?)",
        (user_id, name)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def session_belongs_to_user(session_id: int, user_id: int) -> bool:
    """Security check — user can only access their own sessions"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None

def update_session_name(session_id: int, name: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, session_id)
    )
    conn.commit()
    conn.close()

def delete_session(session_id: int, user_id: int):
    """Delete session — only if it belongs to the user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = ? AND (SELECT user_id FROM sessions WHERE id = ?) = ?",
                   (session_id, session_id, user_id))
    cursor.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    conn.commit()
    conn.close()

# ============================================================
# MULTI-PROVIDER STREAMING (inalterado)
# ============================================================

async def openai_compatible_stream(
    messages: List[Dict[str, str]],
    model_id: str,
    api_key: str,
    base_url: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout_seconds: int = 25
) -> AsyncGenerator[str, None]:
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "HTTP-Referer": config.config.get("settings", {}).get("app_url", "http://localhost"),
        "X-Title": config.config.get("settings", {}).get("app_name", "InesBot"),
        "Accept": "text/event-stream"
    }

    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True
    }

    # Compound/agentic models: generous total timeout, normal connect timeout
    # sock_read=None means wait indefinitely between chunks (model is thinking/searching)
    timeout = aiohttp.ClientTimeout(
        total=timeout_seconds,
        connect=10,
        sock_read=timeout_seconds  # wait this long for first chunk
    )
    full_response = ""
    chunks_received = 0

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                base_url + "/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    yield json.dumps({"error": "API error " + str(resp.status) + ": " + text[:200], "status": "error"})
                    return

                async for line in resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            # Compound models também enviam 'reasoning' — ignorar silenciosamente
                            if not content:
                                content = ''
                            if content:
                                chunks_received += 1
                                full_response += content
                                yield json.dumps({"chunk": content, "full": full_response, "status": "streaming"})
                        except json.JSONDecodeError:
                            continue

        if chunks_received == 0:
            yield json.dumps({"error": "Modelo nao respondeu (timeout ou vazio)", "status": "timeout"})

    except asyncio.TimeoutError:
        if chunks_received > 0:
            # Já recebeu chunks — resposta incompleta mas utilizável
            yield json.dumps({"chunk": "", "full": full_response, "status": "streaming"})
        else:
            yield json.dumps({"error": "Timeout: Modelo demorou mais de " + str(timeout_seconds) + "s a responder", "status": "timeout"})
    except Exception as e:
        yield json.dumps({"error": "Erro de conexao: " + str(e)[:100], "status": "error"})

async def chat_stream(
    messages, model_id, provider, api_key, base_url,
    max_tokens=4096, temperature=0.7, timeout_seconds=25
) -> AsyncGenerator[str, None]:
    api_type = config.get_provider_api_type(provider)
    logger.info(f"Stream: provider={provider}, api_type={api_type}, model={model_id}")
    async for chunk in openai_compatible_stream(messages, model_id, api_key, base_url, max_tokens, temperature, timeout_seconds):
        yield chunk

async def chat_with_fallback_stream(
    messages, model_id, use_fallback, max_tokens=4096, temperature=0.7
) -> AsyncGenerator[str, None]:
    model = config.get_model(model_id)
    if not model:
        yield json.dumps({"error": "Modelo nao encontrado: " + model_id, "status": "error"})
        return

    provider = model.get("provider", "openrouter")
    api_key = config.get_api_key(provider)
    base_url = config.get_base_url(provider)

    if not api_key:
        yield json.dumps({"error": "API key nao configurada para " + provider, "status": "no_key"})
        return

    errors = []
    models_to_try = [model_id]

    if use_fallback:
        fallback_models = config.get_fallback_models(model_id)
        models_to_try.extend(fallback_models)

    for mid in models_to_try:
        try:
            m = config.get_model(mid)
            if not m:
                continue
            p = m.get("provider", "openrouter")
            key = config.get_api_key(p)
            url = config.get_base_url(p)
            mt = m.get("max_tokens", max_tokens)

            if not key:
                errors.append(mid + ": API key nao configurada para " + p)
                continue

            if not config.is_provider_active(p):
                errors.append(mid + ": Provider " + p + " nao esta ativo")
                continue

            if mid != model_id:
                yield json.dumps({"info": "A tentar modelo alternativo: " + m.get("name", mid), "model": mid, "model_name": m.get("name", mid), "status": "fallback"})

            # Modelos compound/agentic precisam de mais tempo (fazem pesquisa web server-side)
            model_timeout = 90 if m.get("groq_builtin_tools") else 25

            success = False
            async for chunk in chat_stream(messages, mid, p, key, url, mt, temperature, timeout_seconds=model_timeout):
                data = json.loads(chunk)
                if "error" in data:
                    errors.append(mid + ": " + data["error"])
                    break
                data["model"] = mid
                data["model_name"] = m.get("name", mid)
                yield json.dumps(data)
                success = True

            if success:
                return
            else:
                errors.append(mid + ": Sem resposta ou erro")

        except Exception as e:
            errors.append(mid + ": " + str(e)[:100])
            continue

    yield json.dumps({"error": "Todos os modelos falharam: " + "; ".join(errors), "status": "all_failed"})


async def openai_compatible_call(
    messages: List[Dict[str, str]],
    model_id: str,
    api_key: str,
    base_url: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    tools: List[Dict] = None,
    timeout_seconds: int = 30,
) -> Optional[Dict]:
    """Chamada não-streaming — necessária para tool calling."""
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "HTTP-Referer": config.config.get("settings", {}).get("app_url", "http://localhost"),
        "X-Title": config.config.get("settings", {}).get("app_name", "InesBot"),
    }
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                base_url + "/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Tool call API error {resp.status}: {text[:200]}")
                    return None
                return await resp.json()
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return None


# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, websocket: WebSocket, message: str):
        try:
            await websocket.send_text(message)
        except Exception:
            pass

manager = ConnectionManager()


# ============================================================
# FASTAPI APP
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_auth_db()
    cleanup_expired_sessions()
    config.reload()   # garantir que lê o config.json mais recente do disco
    yield
    await web_search.close()

app = FastAPI(title="InesBot Multi-Provider API", lifespan=lifespan)

# Serve frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Auth routes ──────────────────────────────────────────────────────────

@app.get("/login")
async def login_page(request: Request):
    """Serve login page — redirect to / if already logged in"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    login_file = FRONTEND_DIR / "login.html"
    if login_file.exists():
        with open(login_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Login page not found</h1>", status_code=500)

@app.post("/login")
async def login_submit(request: Request):
    """Process login form or JSON"""
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()

    blocked, secs = is_rate_limited(ip)
    if blocked:
        return JSONResponse(
            {"error": f"Demasiadas tentativas. Tenta em {secs}s."},
            status_code=429
        )

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
    else:
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))

    user = authenticate_user(username, password)
    record_login_attempt(ip, user is not None)

    if not user:
        logger.warning(f"Login falhado para '{username}' de {ip}")
        return JSONResponse({"error": "Utilizador ou password incorretos."}, status_code=401)

    token = create_session(user["id"])
    logger.info(f"Login com sucesso: {username} de {ip}")

    resp = JSONResponse({"ok": True, "username": user["username"]})
    set_session_cookie(resp, token)
    return resp

@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        invalidate_session(token)
    resp = RedirectResponse(url="/login", status_code=302)
    clear_session_cookie(resp)
    return resp

@app.post("/api/admin/reload-config")
async def reload_config(request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas admins")
    config.reload()
    active = config.get_active_providers()
    return {"status": "ok", "providers": list(active.keys()), "models": len(config.get_available_models())}

@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    from auth import list_users
    return {"users": list_users()}

@app.post("/api/admin/users")
async def admin_create_user(request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    from auth import create_user, get_user_by_username
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    is_admin = bool(body.get("is_admin", False))
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username e password obrigatórios")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password mínimo 6 caracteres")
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Utilizador já existe")
    uid = create_user(username, password, is_admin)
    return {"id": uid, "username": username, "is_admin": is_admin}

@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Não podes apagar a tua própria conta")
    from auth import delete_user, get_user_by_id
    if not get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    delete_user(user_id)
    return {"status": "deleted"}

@app.put("/api/admin/users/{user_id}/password")
async def admin_change_password(user_id: int, request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    from auth import change_password, get_user_by_id
    if not get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    body = await request.json()
    password = body.get("password", "")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password mínimo 6 caracteres")
    change_password(user_id, password)
    return {"status": "ok"}

@app.put("/api/admin/users/{user_id}/toggle-admin")
async def admin_toggle_admin(user_id: int, request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Não podes alterar o teu próprio papel")
    from auth import get_user_by_id, DB_PATH
    import sqlite3
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404)
    new_val = 0 if target["is_admin"] else 1
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (new_val, user_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "is_admin": bool(new_val)}

@app.get("/api/admin/logs")
async def admin_get_logs(request: Request, lines: int = 100):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    log_file = LOGS_DIR / "backend.log"
    if not log_file.exists():
        return {"lines": []}
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}

@app.get("/api/admin/status")
async def admin_status(request: Request):
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403)
    from auth import list_users
    active_providers = config.get_active_providers()
    available_models = config.get_available_models()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions")
    total_sessions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM messages")
    total_messages = cur.fetchone()[0]
    conn.close()
    return {
        "providers": {pid: {"base_url": p["base_url"], "models": sum(1 for m in available_models if m.get("provider") == pid)}
                      for pid, p in active_providers.items()},
        "total_models": len(available_models),
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_users": len(list_users()),
        "ws_connections": len(manager.active_connections)
    }

@app.get("/admin")
async def admin_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso negado")
    admin_file = FRONTEND_DIR / "admin.html"
    if admin_file.exists():
        with open(admin_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="admin.html não encontrado")

@app.get("/api/me")
async def api_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return {"id": user["id"], "username": user["username"], "is_admin": user["is_admin"]}


# ── Main page — requires auth ─────────────────────────────────────────────

@app.get("/")
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return {"status": "InesBot Multi-Provider", "version": "3.0"}

@app.get("/health")
async def health_check(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user["id"],))
        session_count = cursor.fetchone()[0]
        conn.close()
        active_providers = config.get_active_providers()
        return {
            "status": "ok",
            "database": "connected",
            "sessions": session_count,
            "active_providers": list(active_providers.keys()),
            "version": "3.0"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ── Session API — scoped to current user ─────────────────────────────────

@app.get("/api/sessions")
async def api_get_sessions(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    return {"sessions": get_sessions(user["id"])}

@app.post("/api/sessions")
async def api_create_session(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    session_id = create_chat_session(user["id"])
    return {"id": session_id, "name": "Novo Chat"}

@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(status_code=403, detail="Acesso negado")
    delete_session(session_id, user["id"])
    return {"status": "deleted"}

@app.put("/api/sessions/{session_id}")
async def api_rename_session(session_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(status_code=403, detail="Acesso negado")
    body = await request.json()
    name = str(body.get("name", "")).strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Nome vazio")
    update_session_name(session_id, name)
    return {"status": "renamed", "name": name}

@app.get("/api/sessions/{session_id}/messages")
async def api_get_messages(session_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return {"messages": get_messages(session_id)}

@app.get("/api/models")
async def api_get_models(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    return {"models": config.get_available_models()}

@app.get("/api/providers")
async def api_get_providers(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    active = config.get_active_providers()
    return {
        "providers": {
            pid: {
                "base_url": p["base_url"],
                "api_type": p.get("api_type", "openai"),
                "default_model": p.get("default_model", "")
            }
            for pid, p in active.items()
        }
    }


# ── WebSocket — requires auth via cookie ─────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Validate session before accepting
    user = get_current_user(websocket)
    if not user:
        await websocket.close(code=4401)
        logger.warning("WebSocket rejeitado: sem sessão válida")
        return

    await manager.connect(websocket)
    logger.info(f"WebSocket conectado: user={user['username']}")

    try:
        while True:
            data = await websocket.receive_json()

            message = data.get("message", "")
            model_id = data.get("model_id", "")
            session_id = data.get("session_id")
            use_web_search = data.get("use_web_search", False)
            use_fallback = data.get("use_fallback", True)
            document = data.get("document", "")
            summarize_context = data.get("summarize_context", False)
            images = data.get("images", []) or []
            # Validar: só data URLs de imagens, max 4
            images = [
                img for img in images[:4]
                if isinstance(img, str) and img.startswith("data:image/") and len(img) < 8_000_000
            ]

            # Verify session ownership
            if session_id and not session_belongs_to_user(session_id, user["id"]):
                await manager.send_message(websocket, json.dumps({
                    "type": "error", "content": "Acesso negado a esta sessão", "session_id": session_id
                }))
                continue

            # Auto-select model
            auto_selected = False
            if not model_id:
                model_id = config.auto_select_model(message)
                auto_selected = True

            model = config.get_model(model_id)
            model_name = model.get("name", model_id) if model else model_id
            provider = model.get("provider", "openrouter") if model else "openrouter"

            # Create session if needed
            if not session_id:
                session_id = create_chat_session(user["id"], message[:50] if message else "Novo Chat")

            save_message(session_id, "user", message, model_id)
            max_tokens = config.get_model_max_tokens(model_id)

            await manager.send_message(websocket, json.dumps({
                "type": "info",
                "content": "A usar: " + model_name + (" (auto-selecionado)" if auto_selected else ""),
                "model": model_id, "model_name": model_name,
                "provider": provider, "session_id": session_id, "auto_selected": auto_selected
            }))

            await manager.send_message(websocket, json.dumps({
                "type": "thinking",
                "content": "A processar com " + model_name + "...",
                "model": model_id, "model_name": model_name, "session_id": session_id
            }))

            messages = []

            if use_web_search:
                search_results = await web_search.search(message)
                if search_results:
                    messages.append({"role": "system", "content": "Resultados da pesquisa web:\n\n" + search_results})

            if document:
                messages.append({"role": "system", "content": "Documento carregado:\n\n" + document[:8000]})

            messages.append({
                "role": "system",
                "content": "Es o InesBot, um assistente AI amigavel e util. Responde em portugues de Portugal."
            })

            # Definir aqui para usar tanto no contexto como no tool loop abaixo
            current_model_cfg = config.get_model(model_id) or {}

            history = get_messages(session_id)
            context_msgs, summary_used = await build_context(
                history=history,
                summarize=summarize_context,
                stream_fn=chat_with_fallback_stream,
                model_id=model_id,
                use_fallback=use_fallback,
            )

            # Modelos com ferramentas integradas (ex: groq/compound) têm limite
            # de payload mais baixo — enviar só a mensagem actual
            if current_model_cfg.get("groq_builtin_tools"):
                messages = [{"role": "user", "content": message}]
            else:
                messages.extend(context_msgs)

            if summary_used:
                await manager.send_message(websocket, json.dumps({
                    "type": "info",
                    "content": "📝 Contexto resumido automaticamente",
                    "model": model_id, "model_name": model_name,
                    "session_id": session_id
                }))

            # Imagens: converter a última mensagem do user para formato multimodal
            # (formato OpenAI vision, suportado por OpenRouter e compatíveis)
            if images and messages and messages[-1]["role"] == "user":
                content_parts = [{"type": "text", "text": messages[-1]["content"]}]
                for img in images:
                    content_parts.append({"type": "image_url", "image_url": {"url": img}})
                messages[-1]["content"] = content_parts
                logger.info(f"Mensagem com {len(images)} imagem(ns) anexada(s)")

            full_response = ""
            current_model = model_id
            current_model_name = model_name
            fallback_used = False

            # ── Tool calling loop ──────────────────────────────────────────
            # Se o provider suporta tools e não é pesquisa web manual,
            # tenta tool calling primeiro; se falhar, cai para streaming normal
            provider_cfg = config.config.get("providers", {}).get(provider, {})
            
            has_groq_builtin = current_model_cfg.get("groq_builtin_tools", False)

            use_tools = (
                is_tools_supported(provider, provider_cfg)
                and not use_web_search
                and not has_groq_builtin  # compound models não precisam de tool calling manual
            )
            tool_loop_done = False

            if use_tools:
                tools = get_tool_definitions(provider)
                api_key = config.get_api_key(provider)
                base_url = config.get_base_url(provider)
                tool_messages = list(messages)

                MAX_TOOL_ROUNDS = 5  # evitar loops infinitos
                for round_num in range(MAX_TOOL_ROUNDS):
                    response = await openai_compatible_call(
                        tool_messages, model_id, api_key, base_url,
                        max_tokens, tools=tools
                    )
                    if not response:
                        break  # cai para streaming normal

                    tool_calls = extract_tool_calls(response)

                    if not tool_calls:
                        # Modelo respondeu com texto — extrair e terminar
                        choices = response.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content", "")
                            if content:
                                full_response = content
                                tool_loop_done = True
                        break

                    # Modelo quer usar ferramentas
                    tool_names = [tc["name"] for tc in tool_calls]
                    await manager.send_message(websocket, json.dumps({
                        "type": "info",
                        "content": "🔧 A usar: " + ", ".join(tool_names),
                        "model": current_model, "model_name": current_model_name,
                        "session_id": session_id
                    }))

                    # Adicionar resposta do modelo ao histórico de tool messages
                    assistant_msg = response["choices"][0]["message"]
                    tool_messages.append(assistant_msg)

                    # Executar cada tool call e adicionar resultados
                    for tc in tool_calls:
                        result = await handle_tool_call(
                            tc["name"], tc["arguments"],
                            search_fn=web_search.search
                        )
                        logger.info(f"Tool '{tc['name']}' resultado: {str(result)[:100]}")
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": str(result)
                        })

            # ── Streaming final ────────────────────────────────────────────
            # Se tool loop resolveu, stream a resposta; senão stream normal
            if tool_loop_done and full_response:
                # Simular streaming da resposta do tool loop
                chunk_size = 8
                streamed = ""
                for i in range(0, len(full_response), chunk_size):
                    chunk = full_response[i:i+chunk_size]
                    streamed += chunk
                    await manager.send_message(websocket, json.dumps({
                        "type": "chunk",
                        "content": chunk, "full": streamed,
                        "model": current_model, "model_name": current_model_name,
                        "session_id": session_id, "fallback_used": fallback_used
                    }))
                    await asyncio.sleep(0.01)
            else:
                async for chunk_json in chat_with_fallback_stream(messages, model_id, use_fallback, max_tokens):
                    chunk_data = json.loads(chunk_json)

                    if chunk_data.get("status") == "fallback":
                        fallback_used = True
                        current_model = chunk_data.get("model", model_id)
                        current_model_name = chunk_data.get("model_name", model_name)
                        await manager.send_message(websocket, json.dumps({
                            "type": "info",
                            "content": chunk_data.get("info", "A tentar modelo alternativo..."),
                            "model": current_model, "model_name": current_model_name, "session_id": session_id
                        }))
                        continue

                    if "error" in chunk_data:
                        await manager.send_message(websocket, json.dumps({
                            "type": "error", "content": chunk_data["error"],
                            "model": current_model, "model_name": current_model_name,
                            "session_id": session_id, "fallback_used": fallback_used
                        }))
                        break

                    if "chunk" in chunk_data:
                        full_response = chunk_data.get("full", full_response + chunk_data["chunk"])
                        await manager.send_message(websocket, json.dumps({
                            "type": "chunk",
                            "content": chunk_data["chunk"], "full": full_response,
                            "model": chunk_data.get("model", current_model),
                            "model_name": chunk_data.get("model_name", current_model_name),
                            "session_id": session_id, "fallback_used": fallback_used
                        }))

            if full_response:
                save_message(session_id, "assistant", full_response, current_model)
                await manager.send_message(websocket, json.dumps({
                    "type": "done",
                    "content": full_response, "model": current_model,
                    "model_name": current_model_name, "session_id": session_id,
                    "fallback_used": fallback_used
                }))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: " + str(e))
        logger.error(traceback.format_exc())
        await manager.send_message(websocket, json.dumps({
            "type": "error", "content": "Erro interno: " + str(e), "model": "", "session_id": 0
        }))
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
