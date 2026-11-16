from langchain_core.tools import tool

from skill_agent.tools.math_eval import CONSTANTS, FUNCTIONS, CalculationError, evaluate


@tool("calculate")
def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression exactly and return the result.

    Supports + - * / // % ** and parentheses, the constants pi, e and tau, and these functions:
    abs, round, floor, ceil, min, max, factorial, gcd, lcm, sqrt, cbrt, exp, ln, log, log10, log2,
    sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, radians, degrees, hypot.
    """
    return evaluate(expression).display


__all__ = ["CONSTANTS", "FUNCTIONS", "CalculationError", "calculate", "evaluate"]
