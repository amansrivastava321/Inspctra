import requests
from typing import Optional, List, Dict, Any


def _get_settings():
    from qa_ai.config.settings import get_settings
    return get_settings()


class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or _get_settings().ollama_base_url).rstrip("/")

    def chat(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=_get_settings().llm_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def chat_json(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        import json
        response = self.chat(model, prompt, system, temperature)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"raw_response": response, "parse_error": True}

    def embed(self, model: str, text: str) -> List[float]:
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": model, "input": text},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        if "embeddings" in data:
            return data["embeddings"][0]
        return data["embedding"]
