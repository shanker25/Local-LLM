"""Tool system for JARVIS.

Provides the pluggable tool interface, registry, and (in later steps)
the executor, permission layer, and concrete tools.

Only the standard library is used.
"""

from src.tools.base import Tool, ToolError
from src.tools.registry import ToolRegistry

__all__ = ["Tool", "ToolError", "ToolRegistry"]