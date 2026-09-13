import os
import time
import json
from typing import Dict, Any, List, Optional, AsyncIterator, Union, Type, TypeVar
from pydantic import BaseModel
import requests

from core.ai.base import AIProvider, ChatMessage, ToolDefinition, ToolCall, AIResponse, encode_image_to_base64
from core.privacy import PrivacyFilter, PrivacyMode, PrivacyViolationError

T = TypeVar("T", bound=BaseModel)


class CloudAIProvider(AIProvider):
    """External cloud AI provider (OpenAI / Gemini compatible)."""

    def __init__(
        self,
        provider_name: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        privacy_mode: str = "local_only",
        timeout: float = 8.0,
    ):
        self.provider_name = provider_name.lower()
        self.privacy_mode = privacy_mode
        self.timeout = timeout

        if self.provider_name == "openai":
            self.model = model or "gpt-4o-mini"
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            self.endpoint = "https://api.openai.com/v1/chat/completions"
        elif self.provider_name == "gemini":
            self.model = model or "gemini-flash-latest"
            raw_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
            self.api_key = raw_key.strip().rstrip(".")
            self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        else:
            self.model = model or "default"
            self.api_key = api_key
            self.endpoint = ""

    @property
    def name(self) -> str:
        return self.provider_name

    @property
    def is_available(self) -> bool:
        """Check if cloud AI is permitted by privacy mode and has API key."""
        if not PrivacyFilter.check_cloud_allowed(self.privacy_mode):
            return False
        return bool(self.api_key)

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model,
            "privacy_mode": self.privacy_mode,
            "has_key": bool(self.api_key),
            "allowed": PrivacyFilter.check_cloud_allowed(self.privacy_mode)
        }

    async def text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Provider-agnostic text generation."""
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt))
        resp = self.chat(messages, timeout=kwargs.get("timeout", self.timeout))
        return resp.content or ""

    async def vision(
        self,
        prompt: str,
        images: List[Union[bytes, str]],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Provider-agnostic multimodal image-text generation."""
        if not PrivacyFilter.check_cloud_allowed(self.privacy_mode):
            raise PrivacyViolationError(
                f"Cloud vision blocked: privacy mode '{self.privacy_mode}' prohibits sending visual data to external cloud."
            )
        encoded_images = [encode_image_to_base64(img) for img in images]
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt, images=encoded_images))
        resp = self.chat(messages, timeout=kwargs.get("timeout", self.timeout))
        return resp.content or ""

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[Union[bytes, str]]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream generated text tokens."""
        if images:
            full_text = await self.vision(prompt, images, system_prompt=system_prompt, **kwargs)
        else:
            full_text = await self.text(prompt, system_prompt=system_prompt, **kwargs)

        for chunk in full_text.split(" "):
            yield chunk + " "

    async def structured_output(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        images: Optional[List[Union[bytes, str]]] = None,
        **kwargs,
    ) -> T:
        """Generate typed structured output conforming to a Pydantic schema."""
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        instructions = (
            f"{system_prompt or ''}\n"
            f"You must respond ONLY with valid JSON matching this schema:\n{schema_json}\n"
            f"Do not include markdown fences, comments, or extra text."
        )
        if images:
            raw_text = await self.vision(prompt, images, system_prompt=instructions, **kwargs)
        else:
            raw_text = await self.text(prompt, system_prompt=instructions, **kwargs)

        clean = raw_text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        data = json.loads(clean)
        return schema.model_validate(data)

    def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout: Optional[float] = None,
    ) -> AIResponse:
        t0 = time.time()
        eff_timeout = timeout or self.timeout

        # 1. Authoritative Privacy Check & Redaction
        raw_msgs = [m.model_dump() for m in messages]
        sanitized_msgs = PrivacyFilter.prepare_for_cloud(raw_msgs, self.privacy_mode)

        if not self.api_key:
            raise RuntimeError(f"Cloud provider {self.provider_name} is missing an API key.")

        # 2. Call OpenAI or Gemini API
        if self.provider_name == "openai":
            return self._call_openai(sanitized_msgs, tools, temperature, max_tokens, eff_timeout, t0)
        elif self.provider_name == "gemini":
            return self._call_gemini(sanitized_msgs, tools, temperature, max_tokens, eff_timeout, t0)
        else:
            return self._call_generic_cloud(sanitized_msgs, tools, temperature, max_tokens, eff_timeout, t0)

    def _call_openai(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]],
        temperature: float,
        max_tokens: int,
        timeout: float,
        t0: float
    ) -> AIResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        openai_msgs = []
        for m in messages:
            images = m.get("images", [])
            if images:
                content_parts = [{"type": "text", "text": m["content"]}]
                for img in images:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                    })
                openai_msgs.append({"role": m["role"], "content": content_parts})
            else:
                openai_msgs.append({"role": m["role"], "content": m["content"]})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": openai_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            formatted_tools = []
            for t in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters
                    }
                })
            payload["tools"] = formatted_tools

        resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)
        latency = round((time.time() - t0) * 1000, 1)

        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text}")

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})

        tool_calls: List[ToolCall] = []
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=args, id=tc.get("id")))

        return AIResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            provider="openai",
            model=self.model,
            latency_ms=latency,
            raw_response=data
        )

    def _call_gemini(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]],
        temperature: float,
        max_tokens: int,
        timeout: float,
        t0: float
    ) -> AIResponse:
        url = f"{self.endpoint}?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            for img in m.get("images", []):
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img
                    }
                })
            contents.append({"role": role, "parts": parts})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency = round((time.time() - t0) * 1000, 1)

        if resp.status_code != 200:
            raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text}")

        data = resp.json()
        text_content = None
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text_content = "".join([p.get("text", "") for p in parts if "text" in p])
        except Exception:
            pass

        return AIResponse(
            content=text_content,
            tool_calls=[],
            provider="gemini",
            model=self.model,
            latency_ms=latency,
            raw_response=data
        )

    def _call_generic_cloud(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]],
        temperature: float,
        max_tokens: int,
        timeout: float,
        t0: float
    ) -> AIResponse:
        latency = round((time.time() - t0) * 1000, 1)
        return AIResponse(
            content="Cloud response simulated or provider not directly connected.",
            tool_calls=[],
            provider=self.provider_name,
            model=self.model,
            latency_ms=latency
        )

