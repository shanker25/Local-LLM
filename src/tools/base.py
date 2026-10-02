"""Base interface for JARVIS tools.

A Tool is a small, self-describing unit of capability. Every tool declares
its name, a plain-English description, a JSON-schema parameter definition,
and an `execute` method that returns a structured result.

The executor (added in a later step) is the only code that calls
`Tool.execute`. Nothing else in JARVIS is allowed to bypass that path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolError(Exception):
    """Raised for tool-level programming errors.

    Ordinary runtime failures (missing file, not a git repo, HTTP error)
    must NOT raise this. Tools return `{"success": False, "error": ...}`
    instead. `ToolError` is reserved for things that indicate a bug in
    the tool itself or a misuse of the registry/executor.
    """


class Tool(ABC):
    """Abstract base class for all JARVIS tools.

    Subclasses must define:
        name        -- unique lowercase identifier, [a-z0-9_]+
        description -- short, plain-English explanation for the LLM
        schema      -- JSON-schema-style parameter definition

    Subclasses must implement:
        execute(arguments) -> dict
    """

    #: Unique lowercase identifier, e.g. "read_file".
    name: str = ""

    #: Short, plain-English explanation shown to the LLM.
    description: str = ""

    #: JSON-schema-style parameter description.
    #:
    #: Shape:
    #:     {
    #:         "type": "object",
    #:         "properties": { ... },
    #:         "required": [ ... ],
    #:         "additionalProperties": False,
    #:     }
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    # ---- contract ------------------------------------------------------

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run the tool with validated arguments.

        Returns a dict with at least:
            {
                "success": bool,
                "result": Any,
                "error": str | None,
            }

        Ordinary failures must return `success=False` and populate
        `error`, not raise. This keeps the tool loop predictable.
        """
        raise NotImplementedError

    # ---- helpers -------------------------------------------------------

    def to_ollama_tool(self) -> dict[str, Any]:
        """Return this tool in Ollama's native tool-calling format.

        Format reference:
            {"type": "function",
             "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }

    def validate_definition(self) -> None:
        """Raise ToolError if this tool's metadata is malformed.

        Called by the registry at registration time. This catches
        mistakes early -- before the tool ever reaches the LLM.
        """
        if not isinstance(self.name, str) or not self.name:
            raise ToolError(
                f"{type(self).__name__}: 'name' must be a non-empty string."
            )
        if self.name != self.name.lower():
            raise ToolError(
                f"{type(self).__name__}: 'name' must be lowercase "
                f"(got {self.name!r})."
            )
        if not self.name.replace("_", "").isalnum():
            raise ToolError(
                f"{type(self).__name__}: 'name' must contain only "
                f"lowercase letters, digits, and underscores "
                f"(got {self.name!r})."
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise ToolError(
                f"{self.name}: 'description' must be a non-empty string."
            )
        if not isinstance(self.schema, dict):
            raise ToolError(f"{self.name}: 'schema' must be a dict.")
        if self.schema.get("type") != "object":
            raise ToolError(
                f"{self.name}: schema['type'] must be 'object'."
            )
        if "properties" not in self.schema:
            raise ToolError(
                f"{self.name}: schema must contain a 'properties' key."
            )
        if not isinstance(self.schema["properties"], dict):
            raise ToolError(
                f"{self.name}: schema['properties'] must be a dict."
            )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        return f"<Tool {self.name!r}>"