# services/llm_client.py
# Ollama-only LLM client using the native /api/chat endpoint.
# Replaces the previous OpenAI-compatible client.
#
# Environment variables:
#   OLLAMA_BASE_URL    — e.g. http://localhost:11434/api  (default)
#   OLLAMA_TEXT_MODEL  — text generation model (default: qwen2.5:7b)
#   LLM_TIMEOUT        — request timeout in seconds (default: 120)

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """
    Ollama LLM client using the native /api/chat endpoint.

    Environment variables:
        OLLAMA_BASE_URL   — Base URL for Ollama API (default: http://localhost:11434/api)
        OLLAMA_TEXT_MODEL — Model name (default: qwen2.5:7b)
        OLLAMA_KEEP_ALIVE — Keep model loaded in memory (default: 30m)
        LLM_TIMEOUT       — Request timeout in seconds (default: 120)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
        self.timeout = int(timeout or os.getenv("LLM_TIMEOUT", "120"))

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to Ollama and return the assistant's text response.

        Args:
            messages:      List of {role, content} dicts.
            model:         Model name override; falls back to OLLAMA_TEXT_MODEL.
            temperature:   Sampling temperature.
            max_tokens:    Maximum tokens to generate (num_predict in Ollama).
            system_prompt: Optional system message prepended to messages.

        Returns:
            Plain text response from the model.

        Raises:
            RuntimeError: On HTTP errors or unexpected response shape.
        """
        _model = model or self.model

        all_messages: List[Dict[str, str]] = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": _model,
            "messages": all_messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        url = f"{self.base_url}/chat"
        try:
            response = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(f"Ollama HTTP error {exc.response.status_code}: {exc.response.text[:200]}")
            raise RuntimeError(f"Ollama request failed with status {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error(f"Ollama connection error: {exc}")
            raise RuntimeError(f"Ollama connection failed: {exc}") from exc

        try:
            data = response.json()
            text = data["message"]["content"]
            return text.strip()
        except (KeyError, ValueError) as exc:
            logger.error(f"Unexpected Ollama response shape: {response.text[:300]}")
            raise RuntimeError("Could not parse Ollama response") from exc
