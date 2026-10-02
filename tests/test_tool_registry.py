"""Unit tests for ToolRegistry."""

from __future__ import annotations

import unittest

from src.tools.base import Tool, ToolError
from src.tools.registry import ToolRegistry


class _StubTool(Tool):
    """Minimal valid Tool used for registry tests."""

    def __init__(self, name: str, description: str = "stub tool") -> None:
        self.name = name
        self.description = description
        self.schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = ToolRegistry()

    # ---- mutation ------------------------------------------------------

    def test_register_and_get(self) -> None:
        tool = _StubTool("alpha")
        self.reg.register(tool)
        self.assertIs(self.reg.get("alpha"), tool)

    def test_register_rejects_non_tool(self) -> None:
        with self.assertRaises(ToolError):
            self.reg.register("not a tool")  # type: ignore[arg-type]

    def test_register_rejects_duplicate(self) -> None:
        self.reg.register(_StubTool("alpha"))
        with self.assertRaises(ToolError):
            self.reg.register(_StubTool("alpha"))

    def test_register_validates_metadata(self) -> None:
        class Bad(Tool):
            name = "Bad!"
            description = "bad"
            schema = {"type": "object", "properties": {}}
            def execute(self, arguments: dict) -> dict:
                return {}

        with self.assertRaises(ToolError):
            self.reg.register(Bad())

    def test_unregister_removes_tool(self) -> None:
        self.reg.register(_StubTool("alpha"))
        self.reg.unregister("alpha")
        self.assertIsNone(self.reg.get("alpha"))

    def test_unregister_missing_is_silent(self) -> None:
        self.reg.unregister("never_existed")  # must not raise

    def test_clear_removes_all(self) -> None:
        self.reg.register(_StubTool("a"))
        self.reg.register(_StubTool("b"))
        self.reg.clear()
        self.assertEqual(len(self.reg), 0)

    # ---- lookup --------------------------------------------------------

    def test_get_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.reg.get("nope"))

    def test_require_returns_registered_tool(self) -> None:
        tool = _StubTool("alpha")
        self.reg.register(tool)
        self.assertIs(self.reg.require("alpha"), tool)

    def test_require_raises_for_missing(self) -> None:
        with self.assertRaises(ToolError):
            self.reg.require("missing")

    def test_contains(self) -> None:
        self.reg.register(_StubTool("alpha"))
        self.assertIn("alpha", self.reg)
        self.assertNotIn("beta", self.reg)

    def test_iter_yields_tools(self) -> None:
        self.reg.register(_StubTool("a"))
        self.reg.register(_StubTool("b"))
        self.assertEqual({t.name for t in self.reg}, {"a", "b"})

    def test_len(self) -> None:
        self.assertEqual(len(self.reg), 0)
        self.reg.register(_StubTool("a"))
        self.assertEqual(len(self.reg), 1)
        self.reg.register(_StubTool("b"))
        self.assertEqual(len(self.reg), 2)

    # ---- export --------------------------------------------------------

    def test_names_sorted(self) -> None:
        self.reg.register(_StubTool("zeta"))
        self.reg.register(_StubTool("alpha"))
        self.assertEqual(self.reg.names(), ["alpha", "zeta"])

    def test_tools_preserve_registration_order(self) -> None:
        self.reg.register(_StubTool("zeta"))
        self.reg.register(_StubTool("alpha"))
        self.assertEqual([t.name for t in self.reg.tools()], ["zeta", "alpha"])

    def test_describe_for_llm_empty(self) -> None:
        self.assertEqual(self.reg.describe_for_llm(), [])

    def test_describe_for_llm_shape(self) -> None:
        self.reg.register(_StubTool("alpha", description="does alpha things"))
        desc = self.reg.describe_for_llm()
        self.assertEqual(len(desc), 1)
        self.assertEqual(desc[0]["type"], "function")
        self.assertEqual(desc[0]["function"]["name"], "alpha")
        self.assertEqual(desc[0]["function"]["description"], "does alpha things")
        self.assertEqual(desc[0]["function"]["parameters"]["type"], "object")


if __name__ == "__main__":
    unittest.main()