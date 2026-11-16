# Project brief for the coding assistant

This file is the instruction document given to the AI coding assistant (Claude Code) used on this
project. It is kept in the repository as part of the AI usage disclosure the task asks for.

## Goal

Build a prototype multi-skill agent for the I4Twins AI Engineer task. It takes a free-form prompt
(English or Persian), routes it to one or two of four skills (summarizer, translator, calculator,
general chat), runs them and returns one answer. The evaluation focuses on routing accuracy, prompt
quality, the calculator's real tool use, graph design, code clarity, documentation, Persian
handling and edge cases (ambiguous, no-skill, multi-skill).

## Hard constraints from the brief

- LangGraph: at least one routing node plus skill execution nodes.
- Router output must be structured and validated with Pydantic.
- The calculator must compute with a real tool, never with the LLM.
- Up to 2 skills per prompt; explain how they are combined.
- A defined fallback for ambiguous and no-skill prompts.
- Free-tier LLM provider and a model of at most 35B parameters.
- A CLI is enough. Do not build a web API (FastAPI). No memory, database or auth.

## Design decisions (mine, to be followed)

- **Skills are plugins.** A registry is the single source of truth; the router prompt, the
  router's output validation and the graph nodes are generated from it. Adding a skill must not
  require touching the graph.
- **Context must not blow up** as skills are added or several run at once:
  - the router sees compact skill cards only, shortlisted to top-k when the catalogue is large;
  - the router reads an excerpt of long messages;
  - output budget shared between parallel skills, intermediates capped in chains;
  - chained steps receive only the previous output;
  - map-reduce summarization and chunked translation for oversized inputs.
- **Parallel vs sequential** is decided by the router (independent tasks vs a chain).
- **Deterministic code around the LLM**: fallback policies, compose and clarify nodes without LLM
  calls, verification where facts can be checked.
- Provider-agnostic client for any OpenAI-compatible endpoint; OpenRouter free tier by default.
- Persian: normalize input, keep the response in the user's language, enforce Persian orthography
  in prompts.
- Interfaces: CLI (primary) and a Streamlit dashboard as an optional extra that calls the agent
  in-process.

## Engineering conventions

- Python 3.11+, `uv`, `src/` layout, type hints everywhere, `mypy --strict`, `ruff` (lint +
  format, line length 100).
- Small modules with one responsibility; comments only where the *why* is not obvious.
- Prompts live in `src/skill_agent/prompts/*.md`, not in code.
- Tests must run offline (scripted chat model); every behaviour gets a test.
- Git: a feature branch per change (`feat/`, `fix/`, `test/`, `docs/`, `ci/`, `chore/`), a pull
  request per branch with a description, merge commits into `main`, Conventional Commits with a body
  explaining the reason when it is not obvious.
- Never commit secrets (`.env`) or the task PDF.

## Commands

```bash
uv sync --all-extras
uv run ruff check && uv run ruff format --check
uv run mypy src dashboard
uv run pytest
uv run skill-agent ask "..."      # needs LLM_API_KEY in .env
uv run skill-agent eval
uv run --extra dashboard streamlit run dashboard/app.py
```
