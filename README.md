<div align="center">

# 🤖 InesAI

**Lightweight multi-provider AI chat — runs on a Raspberry Pi 4**

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square&logo=fastapi)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey?style=flat-square&logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

</div>

---

A self-hosted AI chat interface built for **low-power hardware**. No Docker. No Electron. No Node.js. Just Python, SQLite, and a browser.

Runs comfortably on a **Raspberry Pi 4 (2GB RAM)** and serves multiple users simultaneously, each with their own isolated chat history.

## ✨ Features

- **Real-time streaming** via WebSocket — responses appear word by word
- **Multi-provider with automatic fallback** — if one provider fails or hits rate limits, it transparently tries the next
- **15+ free models** across 5 providers — Groq, Cerebras, Google AI Studio, GitHub Models, Cloudflare Workers AI
- **Auto model selection** — picks the best model for the task based on message content
- **Tool calling (MCP layer)** — `search_web`, `calculate`, `get_datetime` — works with providers that support function calling
- **Context summarisation** — optional switch to summarise old messages instead of dropping them
- **Per-user isolation** — each user sees only their own conversations
- **Session-based auth** — PBKDF2-SHA256 passwords, signed cookies, login rate limiting
- **Admin panel** — manage users, reload config without restart, view live logs
- **Web search** integration (manual switch)
- **File & image upload** — PDF, DOCX, XLSX, images (vision models)
- **Dark/light theme**, mobile-friendly
- **Zero extra dependencies for auth** — Python stdlib only (hashlib, hmac, secrets)

## 🪶 Why lightweight matters

Most self-hosted AI chat solutions (Open WebUI, LibreChat, etc.) require Docker, Node.js build steps, and 2–4 GB of RAM just to start. InesAI is different:

| | InesAI | Open WebUI | LibreChat |
|---|---|---|---|
| RAM at idle | ~120 MB | ~800 MB+ | ~600 MB+ |
| Requires Docker | ✗ | ✓ | ✓ |
| Requires Node.js | ✗ | ✓ | ✓ |
| Python only | ✓ | ✗ | ✗ |
| SQLite (no DB server) | ✓ | ✗ | ✗ |
| Runs on Pi 4 (2GB) | ✓ | ⚠️ tight | ✗ |

The entire stack is **FastAPI + aiohttp + SQLite**. No build step. No container. Unzip, create a venv, run.

## 📋 Requirements

- Raspberry Pi 4 (2GB+ RAM) or any Linux machine
- Python 3.11+
- nginx (for reverse proxy)
- At least one free API key (see below)

## 🔑 Free API providers

All of these have **free tiers** with no credit card required:

| Provider | Sign up | Models | Speed |
|---|---|---|---|
| [Cerebras](https://cloud.cerebras.ai) | Free — 1M tokens/day | Llama 3.1 8B, GPT-OSS 120B | ⚡⚡⚡ |
| [Groq](https://console.groq.com) | Free — daily limits | Llama 3.3 70B, Qwen QwQ 32B | ⚡⚡⚡ |
| [Google AI Studio](https://aistudio.google.com/apikey) | Free — generous daily | Gemini 2.5 Flash, Gemini 2.5 Pro | ⚡⚡ |
| [GitHub Models](https://github.com/marketplace/models) | Free — rate limited | GPT-4o, Llama 3.3, Mistral Large | ⚡⚡ |
| [Cloudflare Workers AI](https://dash.cloudflare.com) | Free tier | Llama 4 Scout, Qwen3 32B | ⚡⚡ |

Paid providers also supported: Moonshot/Kimi, Anthropic, OpenAI, DeepSeek, Mistral, xAI.

## 🚀 Quick Start

```bash
# 1. Clone or download
git clone https://github.com/Perksls/InesAI.git
cd InesAI

# 2. Install
bash install.sh

# 3. Configure providers
cp config.example.json config.json
nano config.json   # add your API key and set "ativo": true for your provider

# 4. Start
./start.sh
# Open http://YOUR_IP:8001
```

## 🔧 Production (nginx + systemd)

```bash
./install-nginx.sh    # reverse proxy on port 80
./install-systemd.sh  # auto-start on boot
```

## 👥 User management

```bash
python3 manage_users.py create alice password123
python3 manage_users.py create bob   password456 --admin
python3 manage_users.py list
python3 manage_users.py passwd alice newpassword
python3 manage_users.py delete carol
```

Or use the web admin panel at `/admin` (admin users only).

## ⚙️ How fallback works

```
User sends message
        │
        ▼
Auto-select model (or use chosen model)
        │
        ▼
Try model → success → stream response ✓
        │
      fail (rate limit / timeout / error)
        │
        ▼
Try next in fallback_order → success ✓
        │
      fail → ... → show error
```

The `fallback_order` in `config.json` defines the priority. Users see a small notification when fallback kicks in.

## 🔧 MCP / Tool Calling

InesAI includes a `mcp.py` layer that manages context and tools:

- **Context management** — raw history (last 10 messages) or auto-summarise (switch in sidebar)
- **Tools** — `search_web`, `calculate`, `get_current_datetime` — passed to models that support function calling (`mcp: true` in config)
- **External MCP servers** — connect any HTTP MCP server via `mcp_servers` in config (Moonshot/Kimi recommended for best tool calling support)

## 📁 Project structure

```
InesAI/
├── backend/
│   ├── main.py       # FastAPI app, WebSocket, all routes
│   ├── models.py     # Provider config, model selection, fallback
│   ├── auth.py       # Sessions, passwords, rate limiting
│   ├── mcp.py        # Context management + tool calling layer
│   └── search.py     # Web search integration
├── frontend/
│   ├── index.html    # Chat interface
│   ├── login.html    # Login page
│   ├── admin.html    # Admin panel
│   ├── style.css     # Dark/light theme
│   └── app.js        # WebSocket client
├── config.json          # Your config with API keys (git-ignored)
├── config.example.json  # Template — copy to config.json
├── manage_users.py      # CLI user management
├── install.sh           # One-shot installer
└── requirements.txt
```

## 🔒 Security

- Passwords: PBKDF2-SHA256, 260,000 iterations
- Sessions: HMAC-signed cookies (httpOnly, SameSite=Lax)
- Login rate limiting: 5 attempts → 5 min lockout per IP
- Per-user session isolation enforced server-side
- `config.json` and `.env` are git-ignored

Enable HTTPS with Let's Encrypt (`sudo certbot --nginx`) and set `secure=True` on the session cookie in `backend/auth.py` for production.

## 📄 License

MIT
