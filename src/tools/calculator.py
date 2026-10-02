"""Safe arithmetic calculator for JARVIS.

Evaluates arithmetic expressions using Python's ast module with a
strict node whitelist. Never uses eval(). Rejects everything that
isn't a pure arithmetic expression: names, calls, attributes,
subscripts, comprehensions, imports, lambdas, and so on.

Supported:
    +  -  *  /  %  **  ()
    integers and floats

Rejected by design (per Milestone 4 spec):
    - any function call
    - any variable reference
    - any attribute access
    - any subscript
    - any comparison, boolean, bitwise, or assignment operator
    - any string, bytes, list, dict, or set literal
"""

from __future__ import annotations

import ast
import operator
from typing import Any, Callable

from src.tools.base import Tool


# Whitelisted binary operators.
_BIN_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Whitelisted unary operators.
_UNARY_OPS: dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Hard cap on exponentiation to avoid memory blowups like 9**9**9.
_MAX_EXPONENT = 1_000

# Hard cap on the absolute value of any intermediate result.
_MAX_ABS_VALUE = 1e100


class CalculatorError(Exception):
    """Raised for any invalid expression or arithmetic failure."""


def _check_number(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError(f"Unsupported value: {value!r}")
    if abs(value) > _MAX_ABS_VALUE:
        raise CalculatorError("Intermediate result too large.")


def _eval_node(node: ast.AST) -> Any:
    """Recursively evaluate a whitelisted AST node."""

    # Numbers
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError(
                f"Only numbers are allowed (got {type(node.value).__name__})."
            )
        _check_number(node.value)
        return node.value

    # Binary operations
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise CalculatorError(
                f"Operator not allowed: {op_type.__name__}."
            )
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        _check_number(left)
        _check_number(right)

        if op_type is ast.Pow:
            # Exponent must be a small non-negative int for safety.
            if not isinstance(right, int) or isinstance(right, bool):
                raise CalculatorError("Exponent must be an integer.")
            if right < 0:
                raise CalculatorError("Negative exponents are not allowed.")
            if right > _MAX_EXPONENT:
                raise CalculatorError(
                    f"Exponent too large (max {_MAX_EXPONENT})."
                )

        try:
            result = _BIN_OPS[op_type](left, right)
        except ZeroDivisionError:
            raise CalculatorError("Division by zero.")
        except OverflowError:
            raise CalculatorError("Result too large.")
        except Exception as exc:  # noqa: BLE001
            raise CalculatorError(f"Arithmetic error: {exc}")

        _check_number(result)
        return result

    # Unary operations
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise CalculatorError(
                f"Unary operator not allowed: {op_type.__name__}."
            )
        operand = _eval_node(node.operand)
        _check_number(operand)
        result = _UNARY_OPS[op_type](operand)
        _check_number(result)
        return result

    # Everything else is forbidden.
    raise CalculatorError(
        f"Expression contains disallowed syntax: {type(node).__name__}."
    )


def evaluate_expression(expression: str) -> float | int:
    """Evaluate a safe arithmetic expression and return the result.

    Raises CalculatorError on any invalid input or arithmetic failure.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise CalculatorError("Expression must be a non-empty string.")
    if len(expression) > 200:
        raise CalculatorError("Expression too long (max 200 characters).")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"Invalid syntax: {exc.msg}")

    return _eval_node(tree.body)


class CalculatorTool(Tool):
    name = "calculate"
    description = (
        "Evaluate a basic arithmetic expression. Supports + - * / % ** "
        "and parentheses over integers and floats. Does not support "
        "variables, functions, or any other Python syntax."
    )
    schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Arithmetic expression, e.g. '(10 + 5) * 2'.",
            }
        },
        "required": ["expression"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        expression = arguments.get("expression", "")
        try:
            value = evaluate_expression(expression)
        except CalculatorError as exc:
            return {"success": False, "result": None, "error": str(exc)}
        return {"success": True, "result": value, "error": None}