"""
InesBot MCP Layer — Context Management & Tool Abstraction

Responsabilidades:
  1. Context Management
       - Modo raw:    últimas N mensagens em bruto
       - Modo resumo: resumo das mensagens antigas + últimas N recentes

  2. Tool Management
       - Ferramentas do InesBot (search, datetime, calculate)
       - Executar tool calls e devolver resultados
       - Suporte a MCP servers externos (HTTP) — Moonshot e outros

Para activar ferramentas num provider:
  1. config.json: "mcp": true  + "ativo": true  + key válida
  2. main.py: chamar get_tool_definitions() e handle_tool_call() no loop WS

Para ligar um MCP server externo (ex: Moonshot):
  1. config.json: "mcp_servers": [{"name": "x", "url": "https://..."}]
  2. load_mcp_server_tools() descobre as ferramentas automaticamente
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger("inesbot.mcp")

# ── Constantes ────────────────────────────────────────────────────────────────
SUMMARY_THRESHOLD = 10   # mensagens a partir do qual o resumo é activado
RECENT_KEEP       = 4    # mensagens recentes a manter após o resumo
RAW_KEEP          = 10   # mensagens em modo raw


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONTEXT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

async def build_context(
    history: List[Dict[str, Any]],
    summarize: bool,
    stream_fn: Callable,
    model_id: str,
    use_fallback: bool = False,
) -> tuple[List[Dict[str, str]], bool]:
    """
    Constrói as mensagens a enviar ao modelo.
    Retorna (messages, summary_used).
    """
    turns = [m for m in history if m["role"] in ["user", "assistant"]]

    if not summarize or len(turns) <= SUMMARY_THRESHOLD:
        return _raw_context(turns), False

    return await _summarized_context(turns, stream_fn, model_id, use_fallback)


def _raw_context(turns: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [
        {"role": m["role"], "content": m["content"]}
        for m in turns[-(RAW_KEEP * 2):]
    ]


async def _summarized_context(
    turns, stream_fn, model_id, use_fallback
) -> tuple[List[Dict[str, str]], bool]:
    old_turns    = turns[:-RECENT_KEEP]
    recent_turns = turns[-RECENT_KEEP:]

    summary_text = await _generate_summary(old_turns, stream_fn, model_id, use_fallback)

    if not summary_text:
        logger.warning("Resumo falhou — a usar modo raw")
        return _raw_context(turns), False

    messages = [
        {"role": "system", "content": f"Resumo da conversa anterior:\n{summary_text}"}
    ]
    for m in recent_turns:
        messages.append({"role": m["role"], "content": m["content"]})

    logger.info(
        f"Contexto resumido: {len(old_turns)} msgs → "
        f"{len(summary_text)} chars + {len(recent_turns)} recentes"
    )
    return messages, True


async def _generate_summary(turns, stream_fn, model_id, use_fallback) -> str:
    if not turns:
        return ""

    conversation_text = "\n".join([
        f"{m['role'].upper()}: {m['content'][:600]}"
        for m in turns
    ])

    summary_prompt = [
        {
            "role": "system",
            "content": (
                "Resume a conversa seguinte em 3-5 frases concisas em português. "
                "Preserva os pontos mais importantes, decisões e contexto relevante "
                "para continuar a conversa. Sê directo e factual."
            )
        },
        {"role": "user", "content": conversation_text}
    ]

    try:
        summary_text = ""
        async for chunk_json in stream_fn(summary_prompt, model_id, use_fallback, 512):
            chunk_data = json.loads(chunk_json)
            if "chunk" in chunk_data:
                summary_text = chunk_data.get("full", summary_text)
        return summary_text.strip()
    except Exception as e:
        logger.warning(f"Erro ao gerar resumo: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TOOL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Providers que suportam function calling no formato OpenAI
TOOL_PROVIDERS = {"moonshot", "google", "github", "openai", "groq", "anthropic"}

# Ferramentas nativas do InesBot — disponíveis para qualquer provider com mcp:true
INESBOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Pesquisa informação actualizada na web. "
                "Usar quando o utilizador precisa de informação recente, "
                "notícias, preços, ou factos que possam ter mudado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termos de pesquisa em linguagem natural"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Obtém a data e hora actual do servidor.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Avalia expressões matemáticas de forma precisa. "
                "Usar para cálculos que requerem exactidão."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Expressão matemática. Ex: '2**32', '(15*1.23)+7.5'"
                    }
                },
                "required": ["expression"]
            }
        }
    }
]


def is_tools_supported(provider: str, provider_config: Dict[str, Any]) -> bool:
    """Verifica se o provider suporta tool use — lê flag 'mcp' do config."""
    return bool(provider_config.get("mcp", False)) and provider in TOOL_PROVIDERS


def get_tool_definitions(
    provider: str,
    extra_tools: List[Dict] = None
) -> List[Dict]:
    """
    Devolve as definições de ferramentas no formato OpenAI-compatível.
    Todos os providers suportados usam o mesmo formato.
    Pode receber ferramentas extra (ex: vindas de MCP servers externos).
    """
    if provider not in TOOL_PROVIDERS:
        return []

    tools = list(INESBOT_TOOLS)
    if extra_tools:
        tools.extend(extra_tools)

    return tools


async def handle_tool_call(
    tool_name: str,
    tool_args: Dict[str, Any],
    search_fn: Optional[Callable] = None,
) -> str:
    """
    Executa uma tool call e devolve o resultado como string.
    Chamado quando o modelo decide usar uma ferramenta.
    """
    logger.info(f"Tool call: {tool_name} args={tool_args}")

    try:
        if tool_name == "search_web":
            query = tool_args.get("query", "").strip()
            if not query:
                return "Parâmetro 'query' em falta."
            if search_fn:
                result = await search_fn(query)
                return result or "Sem resultados encontrados."
            return "Pesquisa web não disponível nesta sessão."

        elif tool_name == "get_current_datetime":
            now = datetime.now()
            return now.strftime("Data: %d/%m/%Y  Hora: %H:%M:%S")

        elif tool_name == "calculate":
            expression = tool_args.get("expression", "").strip()
            if not expression:
                return "Parâmetro 'expression' em falta."
            # Avaliação segura — sem acesso a builtins perigosos
            safe_chars = set("0123456789+-*/()., ")
            clean = expression.replace("**", "").replace("//", "")
            if not all(c in safe_chars for c in clean):
                return "Expressão inválida — só operações matemáticas básicas permitidas."
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)

        else:
            logger.warning(f"Ferramenta desconhecida: {tool_name}")
            return f"Ferramenta '{tool_name}' não reconhecida."

    except Exception as e:
        logger.error(f"Erro na tool '{tool_name}': {e}")
        return f"Erro ao executar '{tool_name}': {str(e)}"


def extract_tool_calls(response: Any) -> Optional[List[Dict]]:
    """
    Extrai tool calls da resposta do modelo (formato OpenAI-compatível).
    Retorna lista de {id, name, arguments} ou None se não há tool calls.
    Funciona para Moonshot, Google, GitHub, OpenAI, Groq.
    """
    if not response:
        return None

    choices = response.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls")

    if not tool_calls:
        return None

    result = []
    for tc in tool_calls:
        try:
            args_raw = tc.get("function", {}).get("arguments", "{}")
            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            result.append({
                "id":        tc.get("id", ""),
                "name":      tc.get("function", {}).get("name", ""),
                "arguments": args,
            })
        except json.JSONDecodeError:
            logger.warning(f"Não foi possível parsear argumentos da tool: {tc}")
            continue

    return result if result else None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MCP SERVERS EXTERNOS (HTTP)
# ═══════════════════════════════════════════════════════════════════════════════
# Usar quando um provider tem mcp_servers configurados no config.json
# Ex: "mcp_servers": [{"name": "context7", "url": "https://mcp.context7.com/mcp"}]

async def load_mcp_server_tools(
    mcp_servers: List[Dict],
    timeout: int = 5
) -> List[Dict]:
    """
    Descobre e carrega ferramentas de MCP servers externos via HTTP.
    Chama o endpoint /tools/list de cada server e converte para
    formato OpenAI function calling.

    Retorna lista de tool definitions prontas a passar ao modelo.
    Falhas individuais são ignoradas silenciosamente.
    """
    try:
        import aiohttp
    except ImportError:
        logger.warning("aiohttp não disponível — MCP servers externos não carregados")
        return []

    all_tools = []

    for server in mcp_servers:
        name = server.get("name", "unknown")
        url  = server.get("url", "").rstrip("/")
        headers = server.get("headers", {})

        if not url:
            continue

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.post(
                    f"{url}",
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                    headers={"Content-Type": "application/json", **headers}
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"MCP server '{name}' retornou {resp.status}")
                        continue

                    data = await resp.json()
                    tools = data.get("result", {}).get("tools", [])

                    for tool in tools:
                        # Converter para formato OpenAI function calling
                        tool_def = {
                            "type": "function",
                            "function": {
                                "name": f"mcp__{name}__{tool.get('name', '')}",
                                "description": tool.get("description", ""),
                                "parameters": tool.get("inputSchema", {
                                    "type": "object",
                                    "properties": {}
                                })
                            }
                        }
                        all_tools.append(tool_def)

                    logger.info(f"MCP server '{name}': {len(tools)} ferramentas carregadas")

        except asyncio.TimeoutError:
            logger.warning(f"MCP server '{name}' timeout ({timeout}s)")
        except Exception as e:
            logger.warning(f"MCP server '{name}' erro: {e}")

    return all_tools


async def call_mcp_server_tool(
    tool_name: str,
    tool_args: Dict[str, Any],
    mcp_servers: List[Dict],
    timeout: int = 10
) -> str:
    """
    Executa uma ferramenta num MCP server externo.
    O nome da ferramenta segue o formato mcp__<server>__<tool>.
    """
    try:
        import aiohttp
    except ImportError:
        return "aiohttp não disponível"

    # Extrair server e tool do nome
    parts = tool_name.split("__")
    if len(parts) != 3 or parts[0] != "mcp":
        return f"Nome de ferramenta inválido: {tool_name}"

    server_name = parts[1]
    actual_tool = parts[2]

    # Encontrar o server correspondente
    server = next((s for s in mcp_servers if s.get("name") == server_name), None)
    if not server:
        return f"MCP server '{server_name}' não encontrado na configuração"

    url     = server.get("url", "").rstrip("/")
    headers = server.get("headers", {})

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": actual_tool,
                        "arguments": tool_args
                    }
                },
                headers={"Content-Type": "application/json", **headers}
            ) as resp:
                if resp.status != 200:
                    return f"MCP server '{server_name}' retornou {resp.status}"

                data = await resp.json()
                result = data.get("result", {})
                content = result.get("content", [])

                # Extrair texto dos content blocks
                texts = [
                    c.get("text", "") for c in content
                    if c.get("type") == "text" and c.get("text")
                ]
                return "\n".join(texts) if texts else str(result)

    except asyncio.TimeoutError:
        return f"MCP server '{server_name}' timeout"
    except Exception as e:
        logger.error(f"Erro ao chamar MCP server '{server_name}': {e}")
        return f"Erro: {str(e)}"
