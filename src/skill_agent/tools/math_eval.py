"""Safe evaluation of arithmetic expressions.

The expression is parsed with `ast` and evaluated by walking a whitelist of node types, so there
is no `eval()` and no way to reach attributes, imports or builtins. Numbers are kept as exact
`Fraction`s while possible (0.1 + 0.2 == 0.3) and fall back to floats for irrational functions.
"""

from __future__ import annotations

import ast
import math
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from skill_agent.text.persian import to_ascii_digits

Number = Fraction | float

MAX_EXPRESSION_CHARS = 300
MAX_NODES = 150
MAX_RESULT_DIGITS = 2_000
MAX_EXPONENT = 10_000
MAX_FACTORIAL = 1_000
_LOG10_2 = math.log10(2)  # decimal digits per bit


class CalculationError(ValueError):
    pass


@dataclass(frozen=True)
class Evaluation:
    expression: str
    value: Number
    display: str
    exact: bool


def _factorial(n: int) -> int:
    if n > MAX_FACTORIAL:
        raise CalculationError(f"factorial argument is limited to {MAX_FACTORIAL}")
    return math.factorial(n)


def _log(x: float, base: float | None = None) -> float:
    return math.log(x) if base is None else math.log(x, base)


# Functions that operate on exact values / need integers / work on floats.
_EXACT_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
}
_INTEGER_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "factorial": _factorial,
    "gcd": math.gcd,
    "lcm": math.lcm,
}
_FLOAT_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "sqrt": math.sqrt,
    "cbrt": math.cbrt,
    "exp": math.exp,
    "ln": math.log,
    "log": _log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "radians": math.radians,
    "degrees": math.degrees,
    "hypot": math.hypot,
}
FUNCTIONS = sorted({*_EXACT_FUNCTIONS, *_INTEGER_FUNCTIONS, *_FLOAT_FUNCTIONS})
CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e, "tau": math.tau}

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_SYMBOLS = str.maketrans(
    {"×": "*", "✕": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "٫": ".", "٬": "", "٪": "%"}
)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%(?!\s*[\d(.])")
_IMPLICIT_MUL = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*\(|\)\s*\(")


def normalize_expression(text: str) -> str:
    """Accept the notation people actually type: Persian digits, ×, ÷, ^, 1,000 and 20%."""
    expr = to_ascii_digits(text).translate(_SYMBOLS).replace("^", "**")
    expr = _THOUSANDS.sub("", expr)
    expr = _PERCENT.sub(r"(\1/100)", expr)
    expr = _IMPLICIT_MUL.sub(lambda m: f"{m.group(1)}*(" if m.group(1) else ")*(", expr)
    return expr.strip()


def _digits(value: Number) -> int:
    if isinstance(value, Fraction):
        bits = max(value.numerator.bit_length(), value.denominator.bit_length())
        return int(bits * _LOG10_2) + 1
    return 0


def _checked(value: Any) -> Number:
    if isinstance(value, bool):
        raise CalculationError("boolean values are not supported")
    if isinstance(value, int):
        value = Fraction(value)
    if isinstance(value, float):
        if math.isnan(value):
            raise CalculationError("result is not a number")
        if math.isinf(value):
            raise CalculationError("result is too large")
        return value
    if isinstance(value, Fraction):
        if _digits(value) > MAX_RESULT_DIGITS:
            raise CalculationError(f"result exceeds {MAX_RESULT_DIGITS} digits")
        return value
    raise CalculationError(f"unsupported value type: {type(value).__name__}")


def _power(base: Number, exponent: Number) -> Number:
    if isinstance(base, Fraction) and isinstance(exponent, Fraction) and exponent.denominator == 1:
        exp = int(exponent)
        if abs(exp) > MAX_EXPONENT:
            raise CalculationError(f"exponent is limited to {MAX_EXPONENT}")
        if base == 0 and exp < 0:
            raise CalculationError("division by zero")
        bits = max(base.numerator.bit_length(), base.denominator.bit_length())
        if bits * abs(exp) * _LOG10_2 > MAX_RESULT_DIGITS:
            raise CalculationError(f"result exceeds {MAX_RESULT_DIGITS} digits")
        return base**exp
    return math.pow(float(base), float(exponent))


def _as_int(value: Number, func: str) -> int:
    if isinstance(value, Fraction) and value.denominator == 1:
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise CalculationError(f"{func}() needs whole numbers")


class _Evaluator:
    def __init__(self) -> None:
        self.nodes = 0

    def visit(self, node: ast.AST) -> Number:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise CalculationError("expression is too complex")

        match node:
            case ast.Expression(body=body):
                return self.visit(body)
            case ast.Constant(value=value) if isinstance(value, int | float) and not isinstance(
                value, bool
            ):
                return Fraction(repr(value)) if isinstance(value, float) else Fraction(value)
            case ast.Name(id=name):
                if name in CONSTANTS:
                    return CONSTANTS[name]
                raise CalculationError(f"unknown name {name!r}")
            case ast.UnaryOp(op=ast.USub(), operand=operand):
                return _checked(-self.visit(operand))
            case ast.UnaryOp(op=ast.UAdd(), operand=operand):
                return self.visit(operand)
            case ast.BinOp(left=left, op=ast.Pow(), right=right):
                return _checked(_power(self.visit(left), self.visit(right)))
            case ast.BinOp(left=left, op=op, right=right) if type(op) in _BINARY_OPERATORS:
                lhs, rhs = self.visit(left), self.visit(right)
                if rhs == 0 and isinstance(op, ast.Div | ast.FloorDiv | ast.Mod):
                    raise CalculationError("division by zero")
                return _checked(_BINARY_OPERATORS[type(op)](lhs, rhs))
            case ast.Call(func=ast.Name(id=func), args=args, keywords=[]):
                return self._call(func, [self.visit(arg) for arg in args])
        raise CalculationError(f"unsupported syntax: {type(node).__name__}")

    def _call(self, func: str, args: list[Number]) -> Number:
        try:
            if func in _EXACT_FUNCTIONS:
                return _checked(_EXACT_FUNCTIONS[func](*args))
            if func in _INTEGER_FUNCTIONS:
                return _checked(_INTEGER_FUNCTIONS[func](*(_as_int(a, func) for a in args)))
            if func in _FLOAT_FUNCTIONS:
                return _checked(_FLOAT_FUNCTIONS[func](*(float(a) for a in args)))
        except CalculationError:
            raise
        except TypeError as exc:
            raise CalculationError(f"wrong number of arguments for {func}()") from exc
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            raise CalculationError(f"{func}() is undefined for these arguments") from exc
        raise CalculationError(f"unknown function {func!r}")


def format_number(value: Number) -> tuple[str, bool]:
    """Render a result; the flag tells whether the rendering is exact."""
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator), True
        den = value.denominator
        for prime in (2, 5):
            while den % prime == 0:
                den //= prime
        if den == 1:
            text = f"{float(value):.15g}"
            if Fraction(text) == value:
                return text, True
        return f"{float(value):.12g}", False
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value)), False
    return f"{value:.12g}", False


def evaluate(expression: str) -> Evaluation:
    expr = normalize_expression(expression)
    if not expr:
        raise CalculationError("empty expression")
    if len(expr) > MAX_EXPRESSION_CHARS:
        raise CalculationError(f"expression is longer than {MAX_EXPRESSION_CHARS} characters")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CalculationError(f"invalid expression: {expr!r}") from exc
    try:
        value = _Evaluator().visit(tree)
    except CalculationError:
        raise
    except (ZeroDivisionError, OverflowError) as exc:
        raise CalculationError(
            "division by zero" if isinstance(exc, ZeroDivisionError) else "result is too large"
        ) from exc
    except ValueError as exc:
        raise CalculationError("math domain error") from exc
    display, exact = format_number(value)
    return Evaluation(expression=expr, value=value, display=display, exact=exact)
