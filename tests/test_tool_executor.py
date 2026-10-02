"""Unit tests for ToolExecutor."""

from __future__ import annotations

import unittest

from src.tools.base import Tool
from src.tools.executor import ToolExecutor
from src.tools.permissions import Permission, PermissionPolicy
from src.tools.registry import ToolRegistry


class _EchoTool(Tool):
    name = "echo"
    description = "Echo back the argument."
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": arguments["text"], "error": None}


class _FailureTool(Tool):
    name = "always_fails"
    description = "Returns success=False."
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def execute(self, arguments: dict) -> dict:
        return {"success": False, "result": None, "error": "nope"}


class _RaiserTool(Tool):
    name = "raiser"
    description = "Raises an unexpected exception."
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def execute(self, arguments: dict) -> dict:
        raise RuntimeError("boom")


class _NonDictTool(Tool):
    name = "nondict"
    description = "Returns a non-dict result."
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def execute(self, arguments: dict) -> dict:
        return "not a dict"  # type: ignore[return-value]


class _NumberTool(Tool):
    name = "number"
    description = "Requires an integer and a float."
    schema = {
        "type": "object",
        "properties": {
            "n": {"type": "integer"},
            "x": {"type": "number"},
            "flag": {"type": "boolean"},
        },
        "required": ["n"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": arguments, "error": None}


class ToolExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = ToolRegistry()
        self.reg.register(_EchoTool())
        self.reg.register(_FailureTool())
        self.reg.register(_RaiserTool())
        self.reg.register(_NonDictTool())
        self.reg.register(_NumberTool())
        self.policy = PermissionPolicy()
        self.exec_ = ToolExecutor(self.reg, self.policy)

    # ---- happy path ----------------------------------------------------

    def test_unknown_tool_returns_structured_error(self) -> None:
        out = self.exec_.execute("missing", {})
        self.assertFalse(out["success"])
        self.assertEqual(out["tool"], "missing")
        self.assertIn("Unknown tool", out["error"])

    def test_successful_execution(self) -> None:
        out = self.exec_.execute("echo", {"text": "hi"})
        self.assertEqual(
            out, {"success": True, "tool": "echo", "result": "hi", "error": None}
        )

    def test_none_arguments_becomes_empty_dict(self) -> None:
        out = self.exec_.execute("echo", None)
        self.assertFalse(out["success"])  # missing required
        self.assertIn("Missing required argument", out["error"])

    # ---- argument validation ------------------------------------------

    def test_missing_required_argument(self) -> None:
        out = self.exec_.execute("echo", {})
        self.assertFalse(out["success"])
        self.assertIn("Missing required argument: 'text'", out["error"])

    def test_wrong_argument_type(self) -> None:
        out = self.exec_.execute("echo", {"text": 123})
        self.assertFalse(out["success"])
        self.assertIn("must be string", out["error"])

    def test_unexpected_argument_rejected(self) -> None:
        out = self.exec_.execute("echo", {"text": "hi", "extra": 1})
        self.assertFalse(out["success"])
        self.assertIn("Unexpected argument: 'extra'", out["error"])

    def test_boolean_is_not_accepted_as_integer(self) -> None:
        out = self.exec_.execute("number", {"n": True})
        self.assertFalse(out["success"])
        self.assertIn("boolean", out["error"])

    def test_number_accepts_int_for_float_field(self) -> None:
        out = self.exec_.execute("number", {"n": 1, "x": 2})
        self.assertTrue(out["success"])

    def test_number_accepts_float(self) -> None:
        out = self.exec_.execute("number", {"n": 1, "x": 2.5})
        self.assertTrue(out["success"])

    def test_boolean_field(self) -> None:
        out = self.exec_.execute("number", {"n": 1, "flag": True})
        self.assertTrue(out["success"])

    def test_boolean_field_rejects_string(self) -> None:
        out = self.exec_.execute("number", {"n": 1, "flag": "yes"})
        self.assertFalse(out["success"])
        self.assertIn("must be boolean", out["error"])

    # ---- tool-reported failures ---------------------------------------

    def test_tool_reports_success_false(self) -> None:
        out = self.exec_.execute("always_fails", {})
        self.assertFalse(out["success"])
        self.assertEqual(out["error"], "nope")

    def test_tool_raising_exception_is_caught(self) -> None:
        out = self.exec_.execute("raiser", {})
        self.assertFalse(out["success"])
        self.assertIn("Unexpected tool failure", out["error"])

    def test_non_dict_tool_result_is_structured_error(self) -> None:
        out = self.exec_.execute("nondict", {})
        self.assertFalse(out["success"])
        self.assertIn("non-dict result", out["error"])

    # ---- permissions --------------------------------------------------

    def test_read_only_tool_executes_without_callback(self) -> None:
        out = self.exec_.execute("echo", {"text": "hi"})
        self.assertTrue(out["success"])

    def test_write_tool_denied_without_callback(self) -> None:
        self.exec_.set_permission("echo", Permission.WRITE)
        out = self.exec_.execute("echo", {"text": "hi"})
        self.assertFalse(out["success"])
        self.assertIn("Permission denied", out["error"])

    def test_write_tool_allowed_with_approving_callback(self) -> None:
        self.exec_.set_permission("echo", Permission.WRITE)
        exec_ = ToolExecutor(
            self.reg, PermissionPolicy(confirm_callback=lambda n, a: True)
        )
        exec_.set_permission("echo", Permission.WRITE)
        out = exec_.execute("echo", {"text": "hi"})
        self.assertTrue(out["success"])

    def test_destructive_tool_denied_without_callback(self) -> None:
        self.exec_.set_permission("echo", Permission.DESTRUCTIVE)
        out = self.exec_.execute("echo", {"text": "hi"})
        self.assertFalse(out["success"])
        self.assertIn("Permission denied", out["error"])

    def test_default_permission_is_read_only(self) -> None:
        # No set_permission call for "echo"
        self.assertEqual(self.exec_.get_permission("echo"), Permission.READ_ONLY)

    def test_set_get_permission_round_trip(self) -> None:
        self.exec_.set_permission("echo", Permission.WRITE)
        self.assertEqual(self.exec_.get_permission("echo"), Permission.WRITE)

    # ---- ordering guarantees ------------------------------------------

    def test_argument_validation_runs_before_permission_check(self) -> None:
        # If permission ran first, a WRITE tool with no callback would be
        # denied even for bad arguments. We want validation to run first
        # so the error message is about the arguments, not permissions.
        self.exec_.set_permission("echo", Permission.WRITE)
        out = self.exec_.execute("echo", {})
        self.assertFalse(out["success"])
        self.assertIn("Missing required argument", out["error"])


if __name__ == "__main__":
    unittest.main()