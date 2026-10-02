"""Unit tests for the safe arithmetic calculator."""

from __future__ import annotations

import unittest

from src.tools.calculator import CalculatorError, CalculatorTool, evaluate_expression


class EvaluateExpressionTests(unittest.TestCase):
    # ---- happy path ----------------------------------------------------

    def test_simple_addition(self) -> None:
        self.assertEqual(evaluate_expression("2 + 5"), 7)

    def test_multiplication(self) -> None:
        self.assertEqual(evaluate_expression("25 * 48"), 1200)

    def test_division(self) -> None:
        self.assertEqual(evaluate_expression("100 / 4"), 25)

    def test_parentheses(self) -> None:
        self.assertEqual(evaluate_expression("(10 + 5) * 2"), 30)

    def test_operator_precedence(self) -> None:
        self.assertEqual(evaluate_expression("2 + 3 * 4"), 14)

    def test_modulo(self) -> None:
        self.assertEqual(evaluate_expression("17 % 5"), 2)

    def test_power(self) -> None:
        self.assertEqual(evaluate_expression("2 ** 10"), 1024)

    def test_unary_minus(self) -> None:
        self.assertEqual(evaluate_expression("-5 + 3"), -2)

    def test_unary_plus(self) -> None:
        self.assertEqual(evaluate_expression("+5"), 5)

    def test_floats(self) -> None:
        self.assertAlmostEqual(evaluate_expression("1.5 + 2.5"), 4.0)

    def test_nested_parentheses(self) -> None:
        self.assertEqual(evaluate_expression("((2 + 3) * (4 - 1))"), 15)

    # ---- forbidden syntax ---------------------------------------------

    def test_names_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("x + 1")

    def test_function_calls_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("__import__('os')")

    def test_known_function_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("abs(-5)")

    def test_attribute_access_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("(1).__class__")

    def test_subscript_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("[1, 2][0]")

    def test_list_literal_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("[1, 2, 3]")

    def test_dict_literal_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("{'a': 1}")

    def test_string_literal_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("'hello'")

    def test_boolean_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("True")

    def test_comparison_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 < 2")

    def test_boolean_operator_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 and 2")

    def test_bitwise_operator_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 & 2")

    def test_lambda_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("(lambda x: x)(5)")

    def test_conditional_expression_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 if True else 2")

    def test_assignment_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("x = 5")

    def test_semicolon_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1; 2")

    # ---- safety rails -------------------------------------------------

    def test_division_by_zero(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 / 0")

    def test_modulo_by_zero(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 % 0")

    def test_exponent_too_large(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("2 ** 999999")

    def test_negative_exponent_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("2 ** -1")

    def test_expression_too_long(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("1 + " * 100 + "1")

    def test_empty_expression_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("")

    def test_whitespace_only_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("   ")

    def test_non_string_rejected(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression(None)  # type: ignore[arg-type]

    def test_invalid_syntax(self) -> None:
        with self.assertRaises(CalculatorError):
            evaluate_expression("2 +")


class CalculatorToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = CalculatorTool()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "calculate")
        self.assertTrue(self.tool.description)
        self.assertEqual(self.tool.schema["type"], "object")
        self.assertIn("expression", self.tool.schema["properties"])

    def test_valid_execution(self) -> None:
        out = self.tool.execute({"expression": "25 * 48"})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"], 1200)
        self.assertIsNone(out["error"])

    def test_invalid_expression_returns_error(self) -> None:
        out = self.tool.execute({"expression": "x + 1"})
        self.assertFalse(out["success"])
        self.assertIsNotNone(out["error"])

    def test_missing_argument_returns_error(self) -> None:
        out = self.tool.execute({})
        self.assertFalse(out["success"])


if __name__ == "__main__":
    unittest.main()