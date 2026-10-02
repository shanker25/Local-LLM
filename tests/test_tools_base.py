"""Unit tests for the Tool base interface."""

from __future__ import annotations

import unittest

from src.tools.base import Tool, ToolError


class _EchoTool(Tool):
    name = "echo"
    description = "Return the input unchanged."
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": arguments.get("text", ""), "error": None}


class _BadNameTool(Tool):
    name = "Bad Name!"
    description = "invalid name"
    schema = {"type": "object", "properties": {}}

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class _UppercaseNameTool(Tool):
    name = "Echo"
    description = "uppercase name"
    schema = {"type": "object", "properties": {}}

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class _EmptyDescriptionTool(Tool):
    name = "empty_desc"
    description = ""
    schema = {"type": "object", "properties": {}}

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class _BadSchemaTypeTool(Tool):
    name = "bad_schema_type"
    description = "schema type is not object"
    schema = {"type": "array", "properties": {}}

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class _MissingPropertiesTool(Tool):
    name = "missing_props"
    description = "schema lacks properties"
    schema = {"type": "object"}

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class _NonDictPropertiesTool(Tool):
    name = "nondict_props"
    description = "properties is not a dict"
    schema = {"type": "object", "properties": []}

    def execute(self, arguments: dict) -> dict:
        return {"success": True, "result": None, "error": None}


class ToolBaseTests(unittest.TestCase):
    # ---- execute contract ---------------------------------------------

    def test_execute_returns_structured_result(self) -> None:
        out = _EchoTool().execute({"text": "hi"})
        self.assertEqual(out, {"success": True, "result": "hi", "error": None})

    def test_execute_missing_argument_returns_none_content(self) -> None:
        out = _EchoTool().execute({})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"], "")

    # ---- to_ollama_tool -----------------------------------------------

    def test_to_ollama_tool_shape(self) -> None:
        desc = _EchoTool().to_ollama_tool()
        self.assertEqual(desc["type"], "function")
        self.assertEqual(desc["function"]["name"], "echo")
        self.assertEqual(
            desc["function"]["description"], "Return the input unchanged."
        )
        self.assertEqual(desc["function"]["parameters"]["type"], "object")
        self.assertIn("text", desc["function"]["parameters"]["properties"])

    def test_to_ollama_tool_is_pure(self) -> None:
        tool = _EchoTool()
        a = tool.to_ollama_tool()
        b = tool.to_ollama_tool()
        self.assertEqual(a, b)
        self.assertIsNot(a, b)

    # ---- validate_definition ------------------------------------------

    def test_validate_accepts_valid_tool(self) -> None:
        _EchoTool().validate_definition()  # must not raise

    def test_validate_rejects_empty_name(self) -> None:
        class T(Tool):
            name = ""
            description = "x"
            schema = {"type": "object", "properties": {}}
            def execute(self, arguments: dict) -> dict:
                return {}

        with self.assertRaises(ToolError):
            T().validate_definition()

    def test_validate_rejects_uppercase_name(self) -> None:
        with self.assertRaises(ToolError):
            _UppercaseNameTool().validate_definition()

    def test_validate_rejects_bad_name(self) -> None:
        with self.assertRaises(ToolError):
            _BadNameTool().validate_definition()

    def test_validate_rejects_empty_description(self) -> None:
        with self.assertRaises(ToolError):
            _EmptyDescriptionTool().validate_definition()

    def test_validate_rejects_non_object_schema_type(self) -> None:
        with self.assertRaises(ToolError):
            _BadSchemaTypeTool().validate_definition()

    def test_validate_rejects_missing_properties(self) -> None:
        with self.assertRaises(ToolError):
            _MissingPropertiesTool().validate_definition()

    def test_validate_rejects_non_dict_properties(self) -> None:
        with self.assertRaises(ToolError):
            _NonDictPropertiesTool().validate_definition()

    # ---- abstractness --------------------------------------------------

    def test_tool_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError):
            Tool()  # type: ignore[abstract]


if __name__ == "__main__":
    unittest.main()