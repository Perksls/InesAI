"""Models configuration and auto-selection for InesBot"""
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("inesbot.models")


class ModelConfig:

    def __init__(self, config_path: str = "config.json"):
        script_dir = Path(__file__).parent
        possible_paths = [
            Path(config_path),
            script_dir / config_path,
            script_dir.parent / config_path,
            Path("/home/perks/openrouterws") / config_path,
        ]
        self.config_path = next((p for p in possible_paths if p.exists()),
                                script_dir.parent / config_path)
        self.config = self._load_config()
        self.all_models = self._build_model_list()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            logger.info("Config carregado de: " + str(self.config_path))
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning("Config não encontrado: " + str(self.config_path))
        return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "providers": {},
            "settings": {"default_provider": "", "default_model": "", "max_tokens": 4096, "temperature": 0.7},
            "fallback_order": []
        }

    def reload(self):
        self.config = self._load_config()
        self.all_models = self._build_model_list()
        logger.info("Config recarregado")

    def _build_model_list(self) -> List[Dict[str, Any]]:
        """Build flat list of all models from provider-grouped structure."""
        models = []
        for provider_id, provider_data in self.config.get("providers", {}).items():
            for tier in ["free", "paid"]:
                for m in provider_data.get("models", {}).get(tier, []):
                    entry = m.copy()
                    entry["provider"] = provider_id
                    entry["tier"] = tier
                    models.append(entry)
        return models

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        return next((m for m in self.all_models if m["id"] == model_id), None)

    def get_model_max_tokens(self, model_id: str) -> int:
        model = self.get_model(model_id)
        if model and "max_tokens" in model:
            return model["max_tokens"]
        return self.config.get("settings", {}).get("max_tokens", 4096)

    def get_api_key(self, provider: str) -> str:
        keys = self.config.get("providers", {}).get(provider, {}).get("keys", [])
        return next((k for k in keys if k and not k.endswith("_HERE") and len(k) > 10), "")

    def has_api_key(self, provider: str) -> bool:
        return bool(self.get_api_key(provider))

    def is_provider_active(self, provider: str) -> bool:
        prov = self.config.get("providers", {}).get(provider, {})
        return prov.get("ativo", False) and self.has_api_key(provider)

    def is_model_active(self, model_id: str) -> bool:
        model = self.get_model(model_id)
        if not model:
            return False
        return model.get("ativo", True) and self.is_provider_active(model["provider"])

    def get_provider_api_type(self, provider: str) -> str:
        return self.config.get("providers", {}).get(provider, {}).get("api_type", "openai")

    def get_base_url(self, provider: str) -> str:
        return self.config.get("providers", {}).get(provider, {}).get("base_url", "")

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return only models that are active AND whose provider is active."""
        return [m for m in self.all_models if self.is_model_active(m["id"])]

    def get_free_models(self) -> List[Dict[str, Any]]:
        return [m for m in self.get_available_models() if m.get("tier") == "free"]

    def get_active_providers(self) -> Dict[str, Dict[str, Any]]:
        return {pid: pdata for pid, pdata in self.config.get("providers", {}).items()
                if self.is_provider_active(pid)}

    def get_fallback_models(self, model_id: str) -> List[str]:
        """Build fallback list: explicit order first, then all active free models."""
        seen = set()
        result = []

        # 1. Explicit fallback_order
        for entry in self.config.get("fallback_order", []):
            if ":" in entry:
                provider, mid = entry.split(":", 1)
            else:
                m = self.get_model(entry)
                provider = m["provider"] if m else ""
                mid = entry
            if mid != model_id and mid not in seen and self.is_model_active(mid):
                result.append(mid)
                seen.add(mid)

        # 2. All remaining active free models not yet in list
        for m in self.get_free_models():
            mid = m["id"]
            if mid != model_id and mid not in seen:
                result.append(mid)
                seen.add(mid)

        return result

    def auto_select_model(self, message: str, models: List[Dict[str, Any]] = None) -> str:
        if models is None:
            models = self.get_available_models()
        if not models:
            logger.warning("Nenhum modelo disponível")
            return ""

        msg_lower = message.lower()
        keywords = {
            "coding":       ["codigo","python","javascript","html","css","programa","bug","debug","script","funcao","function"],
            "math":         ["equacao","math","calculo","matematica","formula","integral","derivada","probabilidade"],
            "creative":     ["poema","historia","escrita","criativo","poetry","story","write","poesia","conto","romance"],
            "multilingual": ["traduz","translate","chines","ingles","frances","alemao","espanhol","lingua"],
            "long_context": ["resume","pdf","documento","livro","analise","sumario","relatorio"],
            "multimodal":   ["imagem","foto","analisa imagem","video","ficheiro"],
            "fast":         ["rapido","quick","simples","curto","resumo rapido"],
            "agents":       ["agente","automatizar","workflow","tarefa","bot"],
            "ui_ux":        ["interface","design","layout","dashboard","componente","botao","menu","pagina"],
            "reasoning":    ["raciocinio","pensar","logica","deduz","analisa","explica","porque","como funciona"],
        }

        best_model, best_score = None, -1
        for model in models:
            score = 0
            strengths = model.get("strengths", [])
            for category, words in keywords.items():
                if category in strengths:
                    for word in words:
                        if word in msg_lower:
                            score += 2
            if model.get("tier") == "free":
                score += 0.5
            if score > best_score:
                best_score = score
                best_model = model

        if not best_model:
            free = self.get_free_models()
            best_model = free[0] if free else (models[0] if models else None)

        if best_model:
            logger.info(f"Auto-select: {best_model['id']} (score: {best_score})")
            return best_model["id"]
        return ""


# Global instance
config = ModelConfig()
