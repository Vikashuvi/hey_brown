from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class BaseTool(ABC):
    """Abstract base class for strongly typed Brown tools.
    Every tool must validate arguments and have clear permissions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass


class ToolRegistry:
    """Central registry of validated, typed tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        return {name: tool.description for name, tool in self._tools.items()}
