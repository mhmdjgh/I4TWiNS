from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from skill_agent.agent import Agent, AgentResponse
from skill_agent.config import get_settings
from skill_agent.evaluation import CaseResult, evaluate, load_cases
from skill_agent.llm import ConfigurationError
from skill_agent.routing import RoutingDecision
from skill_agent.skills import registry

app = typer.Typer(
    help="Multi-skill agent: summarize, translate, calculate or chat (English and Persian).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

TraceOption = Annotated[bool, typer.Option("--trace/--no-trace", help="Show routing and timings.")]


@app.callback()
def _setup() -> None:
    # Windows consoles default to a legacy code page that cannot print Persian.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _agent() -> Agent:
    try:
        return Agent.from_settings()
    except ConfigurationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


def _decision_table(decision: RoutingDecision) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan")
    table.add_column()
    if decision.needs_clarification:
        table.add_row("skills", "(clarification needed)")
    for i, step in enumerate(decision.skills, 1):
        target = f" -> {step.target_language}" if step.target_language else ""
        table.add_row(f"skill {i}", f"{step.skill}{target}: {step.instruction}")
    table.add_row("mode", decision.mode)
    table.add_row("confidence", f"{decision.confidence:.2f}")
    table.add_row("language", decision.response_language)
    if decision.reasoning:
        table.add_row("reasoning", decision.reasoning)
    return table


def _trace_table(response: AgentResponse) -> Table:
    table = Table(title="trace", title_justify="left")
    for column in ("node", "ms", "in tok", "out tok", "detail"):
        table.add_column(column, justify="right" if "tok" in column or column == "ms" else "left")
    for event in response.trace:
        table.add_row(
            event.node,
            f"{event.elapsed_ms:.0f}",
            str(event.input_tokens or ""),
            str(event.output_tokens or ""),
            event.detail,
        )
    return table


def _print_response(response: AgentResponse, trace: bool) -> None:
    if trace and response.decision is not None:
        console.print(Panel(_decision_table(response.decision), title="routing", expand=False))
    console.print(Panel(Markdown(response.answer), title="answer", border_style="green"))
    if trace:
        for result in response.results:
            for call in result.output.tool_calls if result.output else []:
                console.print(f"[dim]tool {call.name}({call.arguments}) -> {call.output}[/dim]")
        console.print(_trace_table(response))
        tokens_in, tokens_out = response.tokens
        seconds = response.elapsed_ms / 1000
        console.print(f"[dim]{seconds:.1f}s, {tokens_in} in / {tokens_out} out tokens[/dim]")
    if response.error:
        console.print(f"[red]error: {response.error}[/red]")


@app.command()
def ask(
    prompt: Annotated[str, typer.Argument(help="The request, in English or Persian.")],
    trace: TraceOption = True,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full response as JSON.")
    ] = False,
) -> None:
    """Answer a single prompt."""
    response = _agent().run(prompt)
    if as_json:
        print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        _print_response(response, trace)


@app.command()
def chat(trace: TraceOption = False) -> None:
    """Interactive session. Every prompt is handled independently (no conversation memory)."""
    agent = _agent()
    console.print("[dim]Type a request (empty line or Ctrl+C to quit).[/dim]")
    while True:
        try:
            prompt = console.input("[bold]> [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt:
            break
        _print_response(agent.run(prompt), trace)


@app.command()
def route(prompt: Annotated[str, typer.Argument(help="The request to route.")]) -> None:
    """Show only the routing decision (one LLM call)."""
    console.print(_decision_table(_agent().route(prompt)))


@app.command()
def skills() -> None:
    """List registered skills."""
    table = Table("name", "summary", "use when")
    for card in registry.cards():
        table.add_row(card.name, card.summary, card.use_when)
    console.print(table)


@app.command()
def config() -> None:
    """Show the effective configuration (the API key is masked)."""
    settings = get_settings()
    for key, value in settings.model_dump().items():
        shown = "***" if "key" in key and value else value
        console.print(f"[cyan]{key}[/cyan] = {shown}")


@app.command("eval")
def run_eval(
    dataset: Annotated[Path, typer.Option(help="YAML file with labelled prompts.")] = Path(
        "evals/dataset.yaml"
    ),
    output: Annotated[Path, typer.Option(help="Directory for report.md / results.json.")] = Path(
        "evals"
    ),
    full: Annotated[
        bool, typer.Option("--full/--routing-only", help="Run the whole graph, not just routing.")
    ] = False,
    delay: Annotated[
        float, typer.Option(help="Seconds between cases (free-tier rate limits).")
    ] = 3.0,
    only: Annotated[list[str] | None, typer.Option(help="Run only these case ids.")] = None,
) -> None:
    """Measure skill-detection accuracy on the evaluation set."""
    cases = load_cases(dataset)
    if only:
        cases = [case for case in cases if case.id in only]
    agent = _agent()

    def show(result: CaseResult) -> None:
        mark = "[green]ok[/green]  " if result.correct else "[red]MISS[/red]"
        expected = ",".join(result.case.expected)
        predicted = ",".join(result.predicted) or "-"
        console.print(f"{mark} {result.case.id:<34} expected={expected:<24} got={predicted}")

    report = evaluate(agent, cases, full=full, delay_s=delay, on_result=show)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ("report.md", report.to_markdown()),
        ("results.json", report.model_dump_json(indent=2)),
    ):
        (output / name).write_text(content, encoding="utf-8", newline="\n")
    console.print(f"\n[bold]accuracy: {report.accuracy:.0%}[/bold] -> {output / 'report.md'}")


@app.command()
def graph() -> None:
    """Print the agent graph as a Mermaid diagram."""
    print(_agent().mermaid())


if __name__ == "__main__":
    app()
