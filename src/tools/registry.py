"""Tool registry for JARVIS.

The registry is the single source of truth for which tools exist at
runtime. It is deliberately dumb: it stores tools, retrieves them by
name, and produces the list the LLM needs.

It does NOT execute anything, does NOT enforce permissions, and does
NOT know about files, subprocesses, or HTTP. Those concerns live in the
executor (a later step) and in the concrete tools themselves.
"""

from __future__ import annotations

from typing import Iterator

from src.tools.base import Tool, ToolError


class ToolRegistry:
    """An ordered, name-keyed collection of Tool instances."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    # ---- mutation ------------------------------------------------------

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Raises ToolError if:
          - `tool` is not a Tool instance
          - the tool's metadata fails validation
          - a tool with the same name is already registered
        """
        if not isinstance(tool, Tool):
            raise ToolError(f"Not a Tool instance: {tool!r}")
        tool.validate_definition()
        if tool.name in self._tools:
            raise ToolError(f"Tool {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name. Silent if the tool is not present."""
        self._tools.pop(name, None)

    def clear(self) -> None:
        """Remove every registered tool. Useful for tests."""
        self._tools.clear()

    # ---- lookup --------------------------------------------------------

    def get(self, name: str) -> Tool | None:
        """Return the tool with `name`, or None if not registered."""
        return self._tools.get(name)

    def require(self, name: str) -> Tool:
        """Return the tool with `name`, or raise ToolError if missing.

        This is the lookup the executor will use, so a missing tool
        becomes a structured error rather than a silent None.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool: {name!r}")
        return tool

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    # ---- export --------------------------------------------------------

    def names(self) -> list[str]:
        """Sorted list of registered tool names."""
        return sorted(self._tools.keys())

    def tools(self) -> list[Tool]:
        """Registered tools in registration order."""
        return list(self._tools.values())

    def describe_for_llm(self) -> list[dict]:
        """Return Ollama-format tool descriptors for every tool.

        Pass the result directly as the `tools` field of an Ollama
        `/api/chat` request. Empty list if no tools are registered.
        """
        return [tool.to_ollama_tool() for tool in self._tools.values()]