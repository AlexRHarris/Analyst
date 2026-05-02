import httpx


class Ollama:
    def __init__(self, base_url: str, model: str, temperature: float = 0.1):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def generate_json(self, system: str, user: str) -> str:
        with httpx.Client(timeout=120) as c:
            r = c.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": self.temperature},
                },
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
