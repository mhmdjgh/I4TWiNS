from langchain_core.tools import tool

from skill_agent.tools.math_eval import CONSTANTS, FUNCTIONS, CalculationError, evaluate


@tool("calculate")
def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression exactly and return the result.

    Supports + - * / // % ** and parentheses, `CONSTANTS` and `FUNCTIONS`.
    """
    return evaluate(expression).display


__all__ = ["CONSTANTS", "FUNCTIONS", "CalculationError", "calculate", "evaluate"]
