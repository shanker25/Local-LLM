"""Tool executor for JARVIS.

The executor is the only code path that calls `Tool.execute`. It
performs, in order:

    1. Tool lookup via the registry (`require`)
    2. Argument validation against the tool's schema
    3. Permission check via the policy
    4. Execution with error isolation
    5. Structured result packing

Every step produces a `{"success": ..., "tool": ..., "result": ...,
"error": ...}` dict. Ordinary failures never raise; they return
`success=False` with a human-readable `error`.
"""

from __future__ import annotations

from typing import Any

from src.tools.base import Tool, ToolError
from src.tools.permissions import Permission, PermissionPolicy
from src.tools.registry import ToolRegistry


# Mapping of JSON-schema primitive type names to Python types.
_PRIMITIVE_TYPES: dict[str, tuple[type, ...]] = {
    "string":  (str,),
    "integer": (int,),
    "number":  (int, float),
    "boolean": (bool,),
    "array":   (list,),
    "object":  (dict,),
}


class ToolExecutor:
    """Looks up, validates, permission-checks, and runs tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: PermissionPolicy,
        permissions_map: dict[str, Permission] | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy
        # Name -> Permission. Tools absent from this map default to
        # READ_ONLY. Concrete tools will register their levels here.
        self._permissions: dict[str, Permission] = dict(permissions_map or {})

    # ---- permission registry ------------------------------------------

    def set_permission(self, tool_name: str, permission: Permission) -> None:
        self._permissions[tool_name] = permission

    def get_permission(self, tool_name: str) -> Permission:
        return self._permissions.get(tool_name, Permission.READ_ONLY)

    # ---- execution -----------------------------------------------------

    def execute(self, tool_name: str, arguments: dict | None = None) -> dict:
        """Run a tool. Always returns a structured result dict."""
        arguments = dict(arguments or {})

        # 1. lookup
        try:
            tool: Tool = self.registry.require(tool_name)
        except ToolError as exc:
            return self._fail(tool_name, str(exc))

        # 2. argument validation
        error = self._validate_arguments(tool, arguments)
        if error is not None:
            return self._fail(tool_name, error)

        # 3. permission check
        permission = self.get_permission(tool_name)
        if not self.policy.check(tool_name, permission, arguments):
            return self._fail(
                tool_name,
                f"Permission denied for {tool_name!r} "
                f"(level: {permission.value}).",
            )

        # 4. execution with error isolation
        try:
            result = tool.execute(arguments)
        except ToolError as exc:
            return self._fail(tool_name, f"Tool error: {exc}")
        except Exception as exc:  # noqa: BLE001
            return self._fail(tool_name, f"Unexpected tool failure: {exc}")

        # 5. result packing
        if not isinstance(result, dict):
            return self._fail(
                tool_name,
                f"Tool returned non-dict result: {type(result).__name__}",
            )
        return {
            "success": bool(result.get("success", False)),
            "tool": tool_name,
            "result": result.get("result"),
            "error": result.get("error"),
        }

    # ---- helpers -------------------------------------------------------

    def _fail(self, tool_name: str, message: str) -> dict:
        return {"success": False, "tool": tool_name, "result": None, "error": message}

    @staticmethod
    def _validate_arguments(tool: Tool, arguments: dict) -> str | None:
        """Return an error string if `arguments` violates the schema.

        Supports a deliberately narrow subset of JSON-schema:
          - type: "object" with a `properties` map
          - per-property `type`: string|integer|number|boolean|array|object
          - optional `required` list
          - optional `additionalProperties: false`
        This is sufficient for every tool in M4 and keeps the validator
        auditable.
        """
        schema = tool.schema
        if schema.get("type") != "object":
            return f"Internal error: tool {tool.name!r} schema is not an object."

        properties = schema.get("properties", {}) or {}
        required = schema.get("required", []) or []
        additional_ok = schema.get("additionalProperties", True)

        # required keys
        for key in required:
            if key not in arguments:
                return f"Missing required argument: {key!r}."

        # types and unknown keys
        for key, value in arguments.items():
            if key not in properties:
                if additional_ok is False:
                    return f"Unexpected argument: {key!r}."
                continue
            spec = properties[key] or {}
            expected = spec.get("type")
            if not expected:
                continue
            py_types = _PRIMITIVE_TYPES.get(expected)
            if py_types is None:
                continue  # unsupported type spec -> skip rather than reject
            # bool is a subclass of int; require exact match for "integer"/"number"
            if expected in ("integer", "number") and isinstance(value, bool):
                return f"Argument {key!r} must be {expected}, got boolean."
            if not isinstance(value, py_types):
                return (
                    f"Argument {key!r} must be {expected}, "
                    f"got {type(value).__name__}."
                )
        return None