import math

import pytest

from skill_agent.tools import calculate
from skill_agent.tools.math_eval import CalculationError, evaluate, normalize_expression


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", "14"),
        ("(2 + 3) * 4", "20"),
        ("2 ** 10", "1024"),
        ("2 ^ 10", "1024"),
        ("-3 ** 2", "-9"),
        ("7 / 2", "3.5"),
        ("7 // 2", "3"),
        ("7 % 3", "1"),
        ("0.1 + 0.2", "0.3"),
        ("1 / 3 * 3", "1"),
        ("sqrt(1764)", "42"),
        ("factorial(20)", "2432902008176640000"),
        ("gcd(84, 36)", "12"),
        ("round(2.675, 2)", "2.68"),
        ("log(8, 2)", "3"),
        ("abs(-12.5)", "12.5"),
        ("max(3, 9, 4)", "9"),
        ("2350 * 17 / 100", "399.5"),
    ],
)
def test_arithmetic(expression: str, expected: str) -> None:
    assert evaluate(expression).display == expected


def test_exact_rational_results_are_flagged() -> None:
    assert evaluate("0.1 + 0.2").exact
    third = evaluate("1 / 3")
    assert not third.exact and third.display == "0.333333333333"


def test_trigonometry_uses_radians() -> None:
    assert math.isclose(float(evaluate("sin(radians(30))").value), 0.5)
    assert math.isclose(float(evaluate("cos(pi)").value), -1.0)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("۲ + ۳ × ۴", "2 + 3 * 4"),
        ("۱۲٫۵ ÷ ۵", "12.5 / 5"),
        ("1,250,000 - 250,000", "1250000 - 250000"),
        ("20% * 150", "(20/100) * 150"),
        ("۲۰٪", "(20/100)"),
        ("2(3 + 4)", "2*(3 + 4)"),
        ("(1 + 2)(3 + 4)", "(1 + 2)*(3 + 4)"),
        ("log2(8)", "log2(8)"),
        ("10 % 3", "10 % 3"),
        ("max(1, 2)", "max(1, 2)"),
    ],
)
def test_normalization(raw: str, normalized: str) -> None:
    assert normalize_expression(raw) == normalized


def test_persian_input_end_to_end() -> None:
    assert evaluate("۲ + ۳ × ۴").display == "14"
    assert evaluate("۲۵٪ * ۸۴۰").display == "210"


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("1 / 0", "division by zero"),
        ("5 % 0", "division by zero"),
        ("0 ** -1", "division by zero"),
        ("sqrt(-1)", "undefined"),
        ("x + 1", "unknown name"),
        ("foo(3)", "unsupported syntax|unknown function"),
        ("factorial(2.5)", "whole numbers"),
        ("factorial(5000)", "limited"),
        ("9 ** 9 ** 9", "exponent|digits"),
        ("10.0 ** 400.5", "too large"),
        ("", "empty"),
        ("2 +", "invalid"),
        ("1" * 400, "longer"),
    ],
)
def test_rejected_or_failed(expression: str, message: str) -> None:
    with pytest.raises(CalculationError, match=message):
        evaluate(expression)


@pytest.mark.parametrize(
    "payload",
    [
        "__import__('os').system('echo hi')",
        "().__class__.__bases__[0].__subclasses__()",
        "(lambda: 1)()",
        "open('secrets.txt')",
        "[1, 2, 3]",
        "'a' * 3",
        "True + 1",
        "pi.real",
        "abs(x=1)",
        "1 if 1 else 2",
        "2 < 3",
    ],
)
def test_code_injection_is_rejected(payload: str) -> None:
    with pytest.raises(CalculationError):
        evaluate(payload)


def test_node_budget() -> None:
    with pytest.raises(CalculationError, match="complex"):
        evaluate("+".join(["1"] * 140))


def test_langchain_tool_wraps_evaluator() -> None:
    assert calculate.name == "calculate"
    assert calculate.invoke({"expression": "6 * 7"}) == "42"
