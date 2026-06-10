#!/usr/bin/env python3
"""
InesBot Test Suite - Testa auto-select, fallback e max_tokens
Executar na RPi4: python3 test_inesbot.py
"""

import json
import sys
from pathlib import Path

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent / "backend"))
from models import config

def test_auto_select():
    """Testa se o auto-select escolhe o modelo certo"""
    print("=" * 60)
    print("🧪 TESTE 1: AUTO-SELECT DE MODELOS")
    print("=" * 60)

    test_cases = [
        ("Escreve um programa em Python para calcular o factorial", ["coding", "math"]),
        ("Traduz isto para chinês: Olá mundo", ["multilingual"]),
        ("Resume este texto longo de 5000 palavras sobre história de Portugal", ["long_context"]),
        ("Cria um website em HTML e CSS com menu responsivo", ["coding", "agents", "ui_ux"]),
        ("Olá, como estás?", ["chat"]),
        ("Resolve esta equação: x² + 5x + 6 = 0", ["math", "reasoning"]),
        ("Debug este código JavaScript que não funciona", ["coding", "debug"]),
        ("Escreve um poema sobre o mar", ["creative"]),
    ]

    for pergunta, expected_strengths in test_cases:
        model_id = config.auto_select_model(pergunta, config.all_models)
        model = config.get_model(model_id)

        print(f"\n📝 Pergunta: {pergunta[:50]}...")
        print(f"   ✅ Modelo escolhido: {model['name']} ({model_id})")
        print(f"   🏷️  Strengths: {', '.join(model.get('strengths', []))}")

        # Verificar se pelo menos um strength esperado está presente
        matched = any(s in model.get('strengths', []) for s in expected_strengths)
        if matched:
            print(f"   🎯 MATCH: Strengths esperados encontrados!")
        else:
            print(f"   ⚠️  NOTA: Nenhum strength esperado ({', '.join(expected_strengths)})")

def test_max_tokens():
    """Testa se max_tokens está correto por modelo"""
    print("\n" + "=" * 60)
    print("🧪 TESTE 2: MAX_TOKENS POR MODELO")
    print("=" * 60)

    for model in config.all_models:
        model_id = model['id']
        max_t = config.get_model_max_tokens(model_id)
        expected = model.get('max_tokens', 'default (4096)')

        print(f"\n📋 {model['name']} ({model_id})")
        print(f"   max_tokens: {max_t}")

        if model_id == 'google/gemini-2.5-flash' and max_t == 2048:
            print(f"   ✅ CORRETO: Gemini Flash tem 2048 (dentro dos créditos)")
        elif model_id == 'google/gemini-2.5-flash' and max_t != 2048:
            print(f"   ❌ ERRO: Gemini Flash devia ter 2048!")
        elif max_t == 4096:
            print(f"   ✅ CORRETO: 4096 tokens")
        else:
            print(f"   ℹ️  Valor: {max_t}")

def test_fallback():
    """Testa se o fallback_order está correto"""
    print("\n" + "=" * 60)
    print("🧪 TESTE 3: FALLBACK ORDER")
    print("=" * 60)

    # Testar para cada modelo free
    free_models = [m for m in config.all_models if m.get('tier') == 'free']

    for model in free_models:
        model_id = model['id']
        fallback = config.get_fallback_models(model_id)

        print(f"\n🔄 {model['name']} ({model_id})")
        print(f"   Fallback models: {fallback}")

        if len(fallback) > 0:
            print(f"   ✅ Tem {len(fallback)} modelos de fallback")
            # Verificar se todos os fallback existem
            for fb_id in fallback:
                fb_model = config.get_model(fb_id)
                if fb_model:
                    print(f"      ✓ {fb_id} -> {fb_model['name']}")
                else:
                    print(f"      ❌ {fb_id} -> NÃO ENCONTRADO!")
        else:
            print(f"   ⚠️  Sem fallback definido")

def test_providers():
    """Testa se todos os providers têm configuração"""
    print("\n" + "=" * 60)
    print("🧪 TESTE 4: PROVIDERS")
    print("=" * 60)

    providers_needed = set()
    for model in config.all_models:
        providers_needed.add(model.get('provider', 'openrouter'))

    for provider in sorted(providers_needed):
        base_url = config.get_base_url(provider)
        api_key = config.get_api_key(provider)
        has_key = "✅ Configurada" if api_key else "❌ Não configurada"

        print(f"\n🏢 {provider}")
        print(f"   URL: {base_url}")
        print(f"   Key: {has_key}")

        # Listar modelos deste provider
        models = [m['name'] for m in config.all_models if m.get('provider') == provider]
        print(f"   Modelos: {', '.join(models)}")

def test_api_simulation():
    """Simula um pedido API para verificar o payload"""
    print("\n" + "=" * 60)
    print("🧪 TESTE 5: SIMULAÇÃO DE PEDIDO API")
    print("=" * 60)

    test_models = [
        'deepseek/deepseek-chat-v3-0324',
        'google/gemini-2.5-flash',
        'meta-llama/llama-4-scout',
    ]

    for model_id in test_models:
        model = config.get_model(model_id)
        if not model:
            continue

        provider = model.get('provider', 'openrouter')
        api_key = config.get_api_key(provider)
        base_url = config.get_base_url(provider)
        max_tokens = config.get_model_max_tokens(model_id)

        print(f"\n📡 {model['name']}")
        print(f"   Provider: {provider}")
        print(f"   Base URL: {base_url}")
        print(f"   API Key: {'✅' if api_key else '❌'}")
        print(f"   max_tokens: {max_tokens}")

        # Simular payload
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Olá"}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": True
        }
        print(f"   Payload: {json.dumps(payload, indent=6)}")

def main():
    print("\n" + "🤖" * 30)
    print("   INESBOT TEST SUITE v2.1")
    print("   " + "🤖" * 30 + "\n")

    try:
        test_auto_select()
        test_max_tokens()
        test_fallback()
        test_providers()
        test_api_simulation()

        print("\n" + "=" * 60)
        print("✅ TODOS OS TESTES CONCLUÍDOS!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
