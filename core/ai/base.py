from abc import ABC, abstractmethod
import base64
import os
from typing import Dict, Any, List, Optional, AsyncIterator, Union, Type, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


def encode_image_to_base64(image: Union[bytes, str]) -> str:
    """Normalize raw bytes, file paths, data URLs, or raw base64 strings into pure base64."""
    if isinstance(image, bytes):
        return base64.b64encode(image).decode("utf-8")
    if isinstance(image, str):
        if image.startswith("data:image/") and ";base64," in image:
            return image.split(";base64,")[1]
        if os.path.exists(image):
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return image  # assume already base64 string
    raise ValueError(f"Unsupported image type: {type(image)}")


class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    images: List[str] = Field(default_factory=list)  # Optional list of base64-encoded images


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None


class AIResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw_response: Optional[Dict[str, Any]] = None


class AIProvider(ABC):
    """Abstract interface for intelligence providers (Local, OpenAI, Gemini)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'local', 'openai', 'gemini'."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is online, authenticated, and reachable."""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Return information about the active model and hardware state."""
        pass

    @abstractmethod
    async def text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Provider-agnostic text generation."""
        pass

    @abstractmethod
    async def vision(
        self,
        prompt: str,
        images: List[Union[bytes, str]],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Provider-agnostic multimodal image-text understanding."""
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[Union[bytes, str]]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream generated text tokens."""
        pass

    @abstractmethod
    async def structured_output(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        images: Optional[List[Union[bytes, str]]] = None,
        **kwargs,
    ) -> T:
        """Generate typed structured output conforming to a Pydantic schema."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout: float = 8.0,
    ) -> AIResponse:
        """Execute chat inference call (synchronous or bounded for conversational turn)."""
        pass

