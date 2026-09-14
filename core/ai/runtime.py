"""Local AI Inference Runtime Abstraction for Brown.
Provides pluggable runtime backends (Ollama, llama.cpp, OpenAI-compatible servers)
with model lifecycle management, streaming, and hardware resource awareness.
Zero hardcoded machine identities or model names.
"""

from abc import ABC, abstractmethod
import json
import time
import requests
from typing import Dict, Any, List, Optional, AsyncIterator
from core.ai.base import ChatMessage, ToolDefinition, ToolCall, AIResponse


class LocalInferenceRuntime(ABC):
    """Abstract interface for local LLM inference engines."""

    def __init__(self, base_url: str, timeout: float = 6.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the runtime, e.g. 'ollama', 'llamacpp', 'openai_compatible'."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the inference engine is reachable and responding."""
        pass

    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """List available models hosted on this runtime."""
        pass

    @abstractmethod
    def get_model_info(self, model: str) -> Dict[str, Any]:
        """Fetch status and memory profile of a specific model."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout: Optional[float] = None,
    ) -> AIResponse:
        """Execute chat inference."""
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream token chunks as they are generated."""
        pass

    @abstractmethod
    def warm_model(self, model: str, keep_alive: str = "15m") -> bool:
        """Pre-load model weights into VRAM/RAM."""
        pass

    @abstractmethod
    def unload_model(self, model: str) -> bool:
        """Eject model from memory to free VRAM/RAM."""
        pass


class OllamaRuntime(LocalInferenceRuntime):
    """Native Ollama inference runtime backend."""

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            # Check /api/tags or daemon health
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        # Check OpenAI compatible fallback
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=1.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        models = []
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name", "")
                    models.append({
                        "id": name,
                        "name": name,
                        "size": m.get("size", 0),
                        "runtime": "ollama"
                    })
        except Exception:
            pass
        return models

    def get_model_info(self, model: str) -> Dict[str, Any]:
        info = {"model": model, "runtime": "ollama", "loaded": False}
        try:
            resp = requests.get(f"{self.base_url}/api/ps", timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    m_name = m.get("name", "")
                    if model in m_name or m_name in model:
                        info["loaded"] = True
                        info["size_vram"] = m.get("size_vram", 0)
                        info["expires_at"] = m.get("expires_at")
                        break
        except Exception:
            pass
        return info

    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout: Optional[float] = None,
    ) -> AIResponse:
        start_time = time.time()
        req_timeout = timeout or self.timeout

        # Convert messages to Ollama format
        ollama_messages = []
        for m in messages:
            msg_dict = {"role": m.role, "content": m.content}
            if m.images:
                msg_dict["images"] = m.images
            ollama_messages.append(msg_dict)

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=req_timeout)
            latency_ms = (time.time() - start_time) * 1000.0
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return AIResponse(
                    content=content,
                    provider="local",
                    model=model,
                    latency_ms=latency_ms,
                    raw_response=data
                )
            else:
                return AIResponse(
                    content=f"Ollama error: {resp.status_code} {resp.text[:100]}",
                    provider="local",
                    model=model,
                    latency_ms=latency_ms
                )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            return AIResponse(
                content=f"Inference error: {str(e)}",
                provider="local",
                model=model,
                latency_ms=latency_ms
            )

    async def stream(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with requests.post(f"{self.base_url}/api/generate", json=payload, stream=True, timeout=self.timeout) as resp:
                if resp.status_code == 200:
                    for line in resp.iter_lines(decode_unicode=True):
                        if line:
                            data = json.loads(line)
                            yield data.get("response", "")
                            if data.get("done", False):
                                break
        except Exception:
            yield ""

    def warm_model(self, model: str, keep_alive: str = "15m") -> bool:
        """Send empty prompt with keep_alive to load model into memory."""
        try:
            payload = {"model": model, "keep_alive": keep_alive}
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=15.0)
            return resp.status_code == 200
        except Exception:
            return False

    def unload_model(self, model: str) -> bool:
        """Send keep_alive: 0 to eject model from memory."""
        try:
            payload = {"model": model, "keep_alive": 0}
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


class OpenAICompatibleRuntime(LocalInferenceRuntime):
    """Generic OpenAI-compatible inference runtime (llama.cpp, vLLM, LocalAI)."""

    @property
    def name(self) -> str:
        return "openai_compatible"

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        models = []
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "")
                    models.append({"id": mid, "name": mid, "runtime": "openai_compatible"})
        except Exception:
            pass
        return models

    def get_model_info(self, model: str) -> Dict[str, Any]:
        return {"model": model, "runtime": "openai_compatible", "loaded": True}

    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout: Optional[float] = None,
    ) -> AIResponse:
        start_time = time.time()
        req_timeout = timeout or self.timeout

        formatted = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": model,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, timeout=req_timeout)
            latency_ms = (time.time() - start_time) * 1000.0
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                return AIResponse(
                    content=content,
                    provider="local",
                    model=model,
                    latency_ms=latency_ms,
                    raw_response=data
                )
            else:
                return AIResponse(
                    content=f"Runtime error: {resp.status_code}",
                    provider="local",
                    model=model,
                    latency_ms=latency_ms
                )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            return AIResponse(
                content=f"Inference error: {str(e)}",
                provider="local",
                model=model,
                latency_ms=latency_ms
            )

    async def stream(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages, "stream": True}
        try:
            with requests.post(f"{self.base_url}/v1/chat/completions", json=payload, stream=True, timeout=self.timeout) as resp:
                if resp.status_code == 200:
                    for line in resp.iter_lines(decode_unicode=True):
                        if line and line.startswith("data: "):
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            data = json.loads(raw)
                            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
        except Exception:
            yield ""

    def warm_model(self, model: str, keep_alive: str = "15m") -> bool:
        return True

    def unload_model(self, model: str) -> bool:
        return True


def create_local_runtime(runtime_type: str = "ollama", base_url: str = "http://localhost:11434", timeout: float = 6.0) -> LocalInferenceRuntime:
    """Factory function for creating the configured local inference runtime."""
    rtype = (runtime_type or "ollama").lower()
    if rtype in ("ollama", "local"):
        return OllamaRuntime(base_url=base_url, timeout=timeout)
    elif rtype in ("llamacpp", "llama.cpp", "openai_compatible", "openai"):
        return OpenAICompatibleRuntime(base_url=base_url, timeout=timeout)
    else:
        return OllamaRuntime(base_url=base_url, timeout=timeout)
