#!/usr/bin/env python3
"""
InesBot Live API Test - Testa cada modelo com pedido REAL à API
Executar na RPi4: python3 test_models_live.py
"""

import json
import sys
import asyncio
import aiohttp
from pathlib import Path

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent / "backend"))
from models import config

# Cores para terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

async def test_model(model, session):
    """Testa um modelo com pedido real à API"""
    model_id = model["id"]
    name = model["name"]
    provider = model.get("provider", "openrouter")
    max_tokens = config.get_model_max_tokens(model_id)

    api_key = config.get_api_key(provider)
    base_url = config.get_base_url(provider)

    print(f"\n{BOLD}🧪 A testar: {name}{RESET}")
    print(f"   ID: {model_id}")
    print(f"   Provider: {provider}")
    print(f"   max_tokens: {max_tokens}")
    print(f"   API Key: {'✅' if api_key else '❌ NÃO CONFIGURADA'}")

    if not api_key:
        print(f"   {YELLOW}⏭️  IGNORADO: Sem API key{RESET}")
        return {"status": "skipped", "reason": "no_api_key", "model": model_id}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "InesBot Test",
        "Accept": "text/event-stream"
    }

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Responde apenas com a palavra 'OK'"}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "stream": False  # Não stream para ser mais rápido
    }

    url = f"{base_url}/chat/completions"

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with session.post(url, headers=headers, json=payload, timeout=timeout) as resp:
            if resp.status == 200:
                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"   {GREEN}✅ SUCESSO! Resposta: '{content[:50]}...'{RESET}")
                return {"status": "success", "model": model_id, "response": content[:100]}

            elif resp.status == 402:
                text = await resp.text()
                print(f"   {RED}❌ ERRO 402: Sem créditos{RESET}")
                print(f"      {text[:150]}")
                return {"status": "error", "code": 402, "model": model_id, "reason": "no_credits"}

            elif resp.status == 404:
                print(f"   {RED}❌ ERRO 404: Modelo não encontrado{RESET}")
                return {"status": "error", "code": 404, "model": model_id, "reason": "model_not_found"}

            elif resp.status == 401:
                print(f"   {RED}❌ ERRO 401: API key inválida{RESET}")
                return {"status": "error", "code": 401, "model": model_id, "reason": "invalid_key"}

            else:
                text = await resp.text()
                print(f"   {RED}❌ ERRO {resp.status}: {text[:150]}{RESET}")
                return {"status": "error", "code": resp.status, "model": model_id, "reason": text[:100]}

    except asyncio.TimeoutError:
        print(f"   {RED}❌ TIMEOUT: Modelo não respondeu em 30s{RESET}")
        return {"status": "error", "model": model_id, "reason": "timeout"}
    except Exception as e:
        print(f"   {RED}❌ EXCEÇÃO: {str(e)[:150]}{RESET}")
        return {"status": "error", "model": model_id, "reason": str(e)[:100]}

async def main():
    print("\n" + "🤖" * 25)
    print(f"   {BOLD}INESBOT LIVE API TEST{RESET}")
    print("   Testa cada modelo com pedido REAL à API")
    print("   " + "🤖" * 25 + "\n")

    results = {
        "success": [],
        "error": [],
        "skipped": []
    }

    # Separar free e paid
    free_models = [m for m in config.all_models if m.get("tier") == "free"]
    paid_models = [m for m in config.all_models if m.get("tier") == "paid"]

    async with aiohttp.ClientSession() as session:

        # Testar FREE primeiro
        print(f"\n{BOLD}{BLUE}🆓 MODELOS FREE ({len(free_models)}){RESET}")
        print("=" * 60)
        for model in free_models:
            result = await test_model(model, session)
            results[result["status"]].append(result)
            await asyncio.sleep(1)  # Rate limit

        # Testar PAID
        print(f"\n{BOLD}{YELLOW}💰 MODELOS PAID ({len(paid_models)}){RESET}")
        print("=" * 60)
        for model in paid_models:
            result = await test_model(model, session)
            results[result["status"]].append(result)
            await asyncio.sleep(1)

    # Resumo
    print("\n" + "=" * 60)
    print(f"{BOLD}📊 RESUMO{RESET}")
    print("=" * 60)

    total = len(results["success"]) + len(results["error"]) + len(results["skipped"])

    print(f"\n{GREEN}✅ SUCESSO: {len(results['success'])}/{total}{RESET}")
    for r in results["success"]:
        print(f"   ✓ {r['model']}")

    print(f"\n{RED}❌ ERRO: {len(results['error'])}/{total}{RESET}")
    for r in results["error"]:
        reason = r.get('reason', 'unknown')
        code = r.get('code', '')
        print(f"   ✗ {r['model']} (Code: {code}, Reason: {reason})")

    print(f"\n{YELLOW}⏭️  IGNORADOS: {len(results['skipped'])}/{total}{RESET}")
    for r in results["skipped"]:
        print(f"   - {r['model']} ({r.get('reason', '')})")

    # Recomendações
    print("\n" + "=" * 60)
    print(f"{BOLD}🔧 RECOMENDAÇÕES{RESET}")
    print("=" * 60)

    if results["error"]:
        for r in results["error"]:
            model_id = r["model"]
            model = config.get_model(model_id)
            name = model["name"] if model else model_id

            if r.get("code") == 404:
                print(f"\n❌ {name}: Modelo não existe no provider.")
                print(f"   → Verifica o ID no config.json")
            elif r.get("code") == 402:
                print(f"\n❌ {name}: Sem créditos no OpenRouter.")
                print(f"   → Diminui max_tokens ou adiciona créditos")
            elif r.get("reason") == "timeout":
                print(f"\n❌ {name}: Timeout (30s sem resposta).")
                print(f"   → Modelo pode estar offline ou muito lento")
            else:
                print(f"\n❌ {name}: Erro {r.get('code', 'unknown')}")
                print(f"   → {r.get('reason', '')}")

    if not results["error"] and not results["skipped"]:
        print(f"\n{GREEN}🎉 TODOS OS MODELOS FUNCIONAM!{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
