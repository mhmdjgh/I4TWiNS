"""Routing evaluation: run a labelled prompt set through the router and score skill detection."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from skill_agent.agent import Agent
from skill_agent.nodes.execute import CLARIFY
from skill_agent.routing import Mode, RoutingDecision

Category = Literal["clear", "multi", "ambiguous", "no_skill"]
EVAL_DELAY_S = 3.0  # between cases, for free-tier rate limits


class EvalCase(BaseModel):
    id: str
    category: Category
    language: str
    prompt: str
    expected: list[str]
    accept: list[list[str]] = Field(default_factory=list)
    mode: Mode | None = None


class CaseResult(BaseModel):
    case: EvalCase
    predicted: list[str]
    mode: Mode | Literal["-"]
    confidence: float
    correct: bool
    mode_correct: bool | None
    latency_ms: float
    answer: str | None = None
    notes: list[str] = Field(default_factory=list)
    error: str | None = None


class EvalReport(BaseModel):
    model: str
    created_at: str
    full_run: bool
    results: list[CaseResult]

    @property
    def accuracy(self) -> float:
        return sum(r.correct for r in self.results) / len(self.results) if self.results else 0.0

    def by_category(self) -> dict[Category, tuple[int, int]]:
        totals: Counter[Category] = Counter()
        hits: Counter[Category] = Counter()
        for r in self.results:
            totals[r.case.category] += 1
            hits[r.case.category] += r.correct
        return {c: (hits[c], totals[c]) for c in totals}

    def per_label(self) -> dict[str, tuple[float, float, int]]:
        """Precision, recall and support per skill label (multi-label view)."""
        tp: Counter[str] = Counter()
        fp: Counter[str] = Counter()
        fn: Counter[str] = Counter()
        for r in self.results:
            expected, predicted = set(r.case.expected), set(r.predicted)
            for label in predicted & expected:
                tp[label] += 1
            for label in predicted - expected:
                fp[label] += 1
            for label in expected - predicted:
                fn[label] += 1
        labels = sorted(set(tp) | set(fp) | set(fn))
        out = {}
        for label in labels:
            precision = tp[label] / (tp[label] + fp[label]) if tp[label] + fp[label] else 0.0
            recall = tp[label] / (tp[label] + fn[label]) if tp[label] + fn[label] else 0.0
            out[label] = (precision, recall, tp[label] + fn[label])
        return out

    def to_markdown(self) -> str:
        lines = [
            "# Routing evaluation report",
            "",
            f"- Model: `{self.model}`",
            f"- Date: {self.created_at}",
            f"- Cases: {len(self.results)}",
            f"- **Skill-detection accuracy: {self.accuracy:.0%}** "
            f"({sum(r.correct for r in self.results)}/{len(self.results)})",
        ]
        errored = [r for r in self.results if r.error]
        evaluated = [r for r in self.results if not r.error]
        if errored and evaluated:
            hits = sum(r.correct for r in evaluated)
            lines.append(
                f"- {len(errored)} case(s) failed with a provider error and were not routed; "
                f"accuracy on the {len(evaluated)} routed cases: {hits}/{len(evaluated)} "
                f"({hits / len(evaluated):.0%})"
            )
        elif errored:
            lines.append("- **Every case failed with a provider error; nothing was routed.**")
        mode_cases = [r for r in self.results if r.mode_correct is not None]
        if mode_cases:
            lines.append(
                f"- Multi-skill mode (sequential/parallel) correct: "
                f"{sum(bool(r.mode_correct) for r in mode_cases)}/{len(mode_cases)}"
            )
        lines += ["", "## By category", "", "| Category | Correct |", "|---|---|"]
        for category, (hit, total) in self.by_category().items():
            lines.append(f"| {category} | {hit}/{total} |")
        lines += [
            "",
            "## Per skill",
            "",
            "| Label | Precision | Recall | Support |",
            "|---|---|---|---|",
        ]
        for label, (precision, recall, support) in self.per_label().items():
            lines.append(f"| {label} | {precision:.2f} | {recall:.2f} | {support} |")
        lines += [
            "",
            "## Cases",
            "",
            "| | ID | Expected | Predicted | Mode | Conf. | Latency |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in self.results:
            mark = "ok" if r.correct else "miss"
            expected = " → ".join(r.case.expected)
            predicted = " → ".join(r.predicted) or "—"
            if r.error:
                predicted += " (error)"
            lines.append(
                f"| {mark} | `{r.case.id}` | {expected} | {predicted} | {r.mode} | "
                f"{r.confidence:.2f} | {r.latency_ms / 1000:.1f}s |"
            )
        if self.full_run:
            lines += ["", "## Answers", ""]
            for r in self.results:
                lines += [f"### `{r.case.id}`", "", f"> {r.case.prompt.strip()}", ""]
                lines += [f"- _{note}_" for note in r.notes]
                lines += ["", r.answer or f"_(no answer: {r.error})_", ""]
        return "\n".join(lines) + "\n"


def load_cases(path: Path) -> list[EvalCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [EvalCase.model_validate(item) for item in raw]


def labels(decision: RoutingDecision) -> list[str]:
    return [CLARIFY] if decision.needs_clarification else decision.skill_names


def is_correct(case: EvalCase, predicted: list[str]) -> bool:
    return any(sorted(predicted) == sorted(option) for option in [case.expected, *case.accept])


def mode_correct(case: EvalCase, decision: RoutingDecision, predicted: list[str]) -> bool | None:
    if case.mode is None:
        return None
    if decision.mode != case.mode:
        return False
    return case.mode != "sequential" or predicted == case.expected


def evaluate(
    agent: Agent,
    cases: list[EvalCase],
    *,
    full: bool = False,
    delay_s: float = 0.0,
    on_result: Callable[[CaseResult], None] | None = None,
) -> EvalReport:
    results = []
    for i, case in enumerate(cases):
        if i and delay_s:
            time.sleep(delay_s)
        start = time.perf_counter()
        answer = error = None
        notes: list[str] = []
        if full:
            response = agent.run(case.prompt)
            decision, answer, error = response.decision, response.answer, response.error
            skills = set(decision.skill_names) if decision else set()
            notes = [f"{e.node}: {e.detail}" for e in response.trace if e.node in skills]
        else:
            try:
                decision = agent.route(case.prompt)
            except Exception as exc:
                decision, error = None, f"{type(exc).__name__}: {exc}"
        latency = (time.perf_counter() - start) * 1000

        predicted = labels(decision) if decision else []
        result = CaseResult(
            case=case,
            predicted=predicted,
            mode=decision.mode if decision else "-",
            confidence=decision.confidence if decision else 0.0,
            correct=decision is not None and is_correct(case, predicted),
            mode_correct=mode_correct(case, decision, predicted) if decision else None,
            latency_ms=latency,
            answer=answer,
            notes=notes,
            error=error,
        )
        results.append(result)
        if on_result:
            on_result(result)

    return EvalReport(
        model=agent.settings.llm_model,
        created_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        full_run=full,
        results=results,
    )
