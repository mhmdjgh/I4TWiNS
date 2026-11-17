# Skill Agent

[![CI](https://github.com/mhmdjgh/I4TWiNS/actions/workflows/ci.yml/badge.svg)](https://github.com/mhmdjgh/I4TWiNS/actions/workflows/ci.yml)

A multi-skill agent built with **LangGraph**. It takes a free-form prompt in English or Persian,
decides which skill(s) the request needs, runs them, and returns one answer.

| Skill | What it does |
|---|---|
| `summarizer` | Summarizes a given text (map-reduce for texts larger than the context window) |
| `translator` | Translates between Persian, English and other languages, with a deterministic fact check |
| `calculator` | Computes with a real tool: a safe AST evaluator exposed as the LangChain tool `calculate` |
| `general_chat` | Greetings, small talk, general questions, and the fallback |

Up to two skills per prompt, run **in parallel** when the tasks are independent or **in sequence**
when the second works on the first one's output. The agent has a CLI (the main interface) and a
Streamlit dashboard that shows the routing decision, the execution trace and the evaluation.

A real run, with the CLI output abridged:

```text
$ skill-agent ask "متن زیر را خلاصه کن و بعد خلاصه‌اش را به انگلیسی ترجمه کن: شهر اصفهان با پل‌های تاریخی، ..."
routing  summarizer -> translator (sequential)
answer   Isfahan, with its historic bridges, Naqsh-e Jahan Square, and Safavid architecture, is one
         of Iran's top tourist destinations, attracting thousands of domestic and international
         visitors annually, while the recent drying up of the Zayandeh River has damaged the city's
         appearance and tourism-related businesses.
```

---

## Contents

1. [Running it](#1-running-it)
2. [Architecture](#2-architecture)
3. [Routing](#3-routing)
4. [Multi-skill requests](#4-multi-skill-requests)
5. [Fallback behaviour](#5-fallback-behaviour)
6. [Keeping the context window under control](#6-keeping-the-context-window-under-control)
7. [Skills and prompt engineering](#7-skills-and-prompt-engineering)
8. [Persian support](#8-persian-support)
9. [LLM provider and model](#9-llm-provider-and-model)
10. [Evaluation](#10-evaluation)
11. [Code quality and tests](#11-code-quality-and-tests)
12. [Project layout](#12-project-layout)
13. [Known limitations and the road to production](#13-known-limitations-and-the-road-to-production)
14. [Assumptions](#14-assumptions)

---

## 1. Running it

**Prerequisites:** Python 3.11+ and [uv](https://docs.astral.sh/uv/). A free
[OpenRouter](https://openrouter.ai/keys) API key (no credit needed).

```bash
git clone https://github.com/mhmdjgh/I4TWiNS.git
cd I4TWiNS
uv sync                      # core + dev tools
cp .env.example .env         # then set LLM_API_KEY
```

### Environment variables

Only `LLM_API_KEY` is required. Everything else has a default (see [`.env.example`](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `LLM_API_KEY` (or `OPENROUTER_API_KEY`) | – | Provider key |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint |
| `LLM_MODEL` | `nvidia/nemotron-3.5-lightning:free` | Primary model |
| `LLM_FALLBACK_MODEL` | `google/gemma-4-31b-it:free` | Used if the primary fails |
| `LLM_REASONING` | `off` | Hidden reasoning for reasoning models (`off`/`low`/`medium`/`high`); general chat uses `low` |
| `LLM_REASONING_PARAM` | `openrouter` | How the switch is sent: `openrouter` (`reasoning` object), `openai` (`reasoning_effort`) or `none` |
| `LLM_JSON_MODE` / `LLM_SYSTEM_ROLE` | `true` / `true` | Provider quirks (JSON mode, system-role support) |
| `MAX_SKILLS_PER_REQUEST` | `2` | Skills per prompt |
| `CLARIFY_BELOW_CONFIDENCE` | `0.4` | Below this, a non-chat route becomes a clarifying question |
| `SHORTLIST_THRESHOLD` / `SHORTLIST_TOP_K` | `8` / `6` | Router sees only top-k skill cards once there are more than the threshold |
| `CONTEXT_WINDOW`, `MAX_OUTPUT_TOKENS`, `TOTAL_OUTPUT_BUDGET`, `ROUTER_EXCERPT_TOKENS`, `CHUNK_TOKENS` | 16000, 1200, 2000, 700, 2500 | Context budget (see [§6](#6-keeping-the-context-window-under-control)) |

### CLI

```bash
uv run skill-agent ask "What is (17.5 * 42) / 3 + 2^10?"          # answer + routing + trace
uv run skill-agent ask "سلام! حالت چطوره؟" --json                  # full structured response
uv run skill-agent chat                                           # interactive (stateless) loop
uv run skill-agent route "translate this please"                  # routing decision only
uv run skill-agent eval                                           # routing accuracy on evals/dataset.yaml
uv run skill-agent skills | config | graph                        # registry, settings, Mermaid graph
```

> On Windows terminals Persian is printed in logical order and may look reversed. The dashboard
> renders it correctly.

### Dashboard (optional)

```bash
uv run --extra dashboard streamlit run dashboard/app.py
```

A light, minimal, responsive interface (English) with three pages. Prompts and answers can be
English or Persian; Persian answers are laid out right-to-left.

- **Assistant**: a chat-style view with example prompts. Every answer shows the selected skills,
  mode, confidence, latency and tokens, plus a *Behind the scenes* panel. The panel has the
  execution pipeline (parallel skills drawn side by side, time and tokens per node), the routing
  decision with each skill's instruction and span, tool calls, intermediate results of a chain,
  and the raw JSON.
- **How it works**: the request lifecycle, the graph, the skill cards the router sees, and the
  context-protection mechanisms with their current settings.
- **Evaluation**: accuracy, latency, per-category and per-skill results, every case with expected
  vs. selected skills, and the answers of full runs. Re-running saves to `evals/runs/` and never
  overwrites the committed results.

It calls the agent in-process; no web API was built, as the brief asked.

### Docker

```bash
docker build -t skill-agent .
docker run --rm -p 8501:8501 --env-file .env skill-agent                       # dashboard
docker run --rm -it --env-file .env skill-agent skill-agent chat               # CLI
```

---

## 2. Architecture

```mermaid
flowchart TB
    U([prompt]) --> P[preprocess<br/>normalize Persian, detect language]
    P --> R{{router<br/>skill cards → JSON → Pydantic}}
    R -- needs clarification --> C[clarify]
    R -- "Send × n (parallel)" --> A[skill node]
    R -- "Send (first of a chain)" --> A
    A -- "previous output → next input (sequential)" --> B[skill node]
    A --> M[compose]
    B --> M
    A -. calculator .-> T[(calculate tool)]
    C --> E([answer])
    M --> E
```

| Node | LLM call | Responsibility |
|---|---|---|
| `preprocess` | no | Persian normalization (Arabic ي/ك → ی/ک, ZWNJ cleanup), language guess |
| `router` | 1 | Shortlist skill cards, ask for a JSON decision, validate with Pydantic against the registry, apply fallback policies |
| skill nodes (`summarizer`, `translator`, `calculator`, `general_chat`) | 1+ | One node per registered skill; generated from the registry |
| `clarify` | no | Returns the clarifying question |
| `compose` | no | Joins results: the last output of a chain, or titled sections for parallel results |

### Design decisions

| Decision | Why |
|---|---|
| **One node per skill, generated from a registry** | Matches the "routing node + skill execution nodes" shape the brief asks for and keeps the graph readable in LangGraph Studio/the dashboard. A new skill is one module with `@register_skill`; the router prompt, its validation and the graph pick it up automatically. |
| **Router sees *skill cards*, not skill prompts** | A card is ~3 lines (summary, when to use, examples). Full system prompts load only inside their own node (progressive disclosure), which keeps routing cheap as skills are added. |
| **Structured output via prompt + Pydantic, not native tool calling** | Free models differ in function-calling support. JSON + Pydantic validation works on any OpenAI-compatible endpoint; validation errors are sent back to the model for one self-repair. |
| **Validation context instead of a hard-coded `Literal`** | `RoutingDecision.model_validate_json(..., context={"skills": [...], "max_skills": n})` checks names against the live registry, so the schema never changes when skills change. |
| **Deterministic policies after the LLM** | Fallback, clarification and low-confidence handling are code, not prompt instructions, so they hold even when the model ignores a rule. |
| **`Send` for skill inputs** | Each skill node receives a `SkillTask` (request, instruction, target language, optional chained input, output budget), never the whole state. Parallel branches are isolated; results merge through a list reducer. |
| **`compose` and `clarify` without an LLM** | Re-sending outputs to a model just to join them costs a call, adds latency and can alter correct results. |
| **Failures are isolated** | A failing skill becomes an error section; the other branch still answers. A provider outage returns a localized message instead of a stack trace. |

The full LangGraph-compiled graph is printed by `skill-agent graph`.

---

## 3. Routing

The router makes **one LLM call** and returns a `RoutingDecision`:

```json
{
  "reasoning": "Summarize the text, then translate that summary.",
  "skills": [
    {"skill": "summarizer", "instruction": "summarize the Persian text", "target_language": null},
    {"skill": "translator", "instruction": "translate the summary into English", "target_language": "English"}
  ],
  "mode": "sequential",
  "response_language": "fa",
  "confidence": 0.95,
  "needs_clarification": false,
  "clarification_question": null
}
```

Validation (`src/skill_agent/routing.py`):

- skill names normalized (`"Translate"` → `translator`, `"chat"` → `general_chat`) and checked
  against the registry; at most `MAX_SKILLS_PER_REQUEST`;
- `mode` made consistent (one skill → `single`, two skills marked `single` → `parallel`);
- language names mapped to codes (`"Persian"` → `fa`);
- errors are written for the model ("unknown skill name(s) ['poet']; use only: summarizer, …"),
  which gets **one repair attempt**; a reply cut off by the token limit is retried with a larger
  limit.

The prompt ([`prompts/router.md`](src/skill_agent/prompts/router.md)) is few-shot and bilingual,
with rules for the cases that are easy to get wrong: the requested *action* decides the skill,
not the topic ("who invented algebra?" is chat, not calculator); when two skills are sequential vs
parallel; when to ask instead of guess; and treating instructions inside the text to process as
content.

---

## 4. Multi-skill requests

The router chooses the shape, because only it knows whether the tasks depend on each other:

| Mode | When | How it runs | What the user gets |
|---|---|---|---|
| `sequential` | The second skill must work on the first one's output: *"summarize this and translate the summary"*, *"TL;DR of this paragraph in French"* | Only the first node starts. `after_skill` sends **only the previous output plus the user's instruction** (not the original text, the state or history) to the next node. A failed step stops the chain. | The final output, since that is what was asked for. Intermediate results are in the trace and dashboard. |
| `parallel` | Independent tasks: *"translate 'good luck' into Persian, and what is 15% of 3,200?"* | One `Send` per skill in the same superstep. The router can pin each skill's part of the message (`input`), so the translator sees only the phrase and the calculator only the calculation; a pinned span is used only if it occurs verbatim in the message. | Titled sections (`**Translation**`, `**Calculation**`, localized). |

Giving each skill only its own share is not just about context size: in evaluation, a translator that
could see the whole prompt translated the original text instead of the summary (chain) and the
calculation as well as the phrase (parallel).

Why not always chain or always parallelize? Always chaining makes independent tasks slower and
feeds unrelated text into the second skill. Always parallelizing breaks requests like *summarize then
translate*, where the translation would run on the full text instead of on the summary. Both shapes
are in the evaluation set.

---

## 5. Fallback behaviour

| Situation | Behaviour | Why |
|---|---|---|
| No skill fits (*"write a poem about the sea"*) | `general_chat` | It is a conversational request; refusing would be unhelpful. |
| A skill is clearly wanted but its input is missing (*"translate this please"*, *"اینو برام خلاصه کن"*) | Clarifying question, in the user's language | Guessing would produce a useless answer. |
| Router confidence < `CLARIFY_BELOW_CONFIDENCE` for a non-chat skill | Clarifying question | Running the wrong skill confidently is worse than asking. Low-confidence *chat* is kept, since chat already handles vagueness. |
| Router output invalid even after the repair attempt | `general_chat` (confidence 0) | The user still gets an answer; the trace records why. |
| Summarizer receives no real text (< 8 words) | Asks for the text | A second line of defence for the miss found in evaluation (§10). |
| A skill raises (timeout, provider error) | Error section for that skill, other branch still answers | Partial answers beat none. |
| Provider unreachable / rate limited | Localized "model not reachable" message, error in the response | No stack traces for users. |

A clarifying question written in the wrong language (seen once with the real model) is replaced
by a localized default.

---

## 6. Keeping the context window under control

This is the scaling problem the design is built around: as the catalogue grows and more skills
run per request, every call must still fit the model's window. Each risk has its own mechanism
(`src/skill_agent/context/`):

| Risk | Mechanism |
|---|---|
| **The router prompt grows with the number of skills** | The router sees only compact skill cards. Above `SHORTLIST_THRESHOLD` skills, a bilingual lexical `Shortlister` (keyword phrases plus IDF-weighted overlap, no LLM call) keeps only the `SHORTLIST_TOP_K` most relevant cards. The fallback card is always kept. **Tested:** router prompt size stays flat for 10, 50 and 200 registered skills; the right skill survives shortlisting in a 54-skill catalogue for English and Persian prompts. |
| **A long message is sent to the router** | The router reads a head/tail excerpt. The request is at the start or end; the long middle is the document, which routing does not need. |
| **Several skills write into one answer** | `ContextBudget.output_per_step`: parallel steps share `TOTAL_OUTPUT_BUDGET`. In a chain each intermediate output is capped at `MAX_OUTPUT_TOKENS`, so step *n+1*'s input is bounded by construction. |
| **Chained steps pile up history** | The next step receives only the previous output and the user's instruction, never the original text or the state. Parallel branches are isolated by `Send` and get only their pinned span. |
| **A text larger than the window must be summarized** | Map-reduce: chunk → summarize each part → merge, repeating the reduce while partials are still too long. **Tested:** every call fits a deliberately small window. |
| **A text larger than the window must be translated** | Chunk-by-chunk translation, joined in order. |
| **Chat/calculator get a huge input** | Excerpt to the room left in the window. |
| **Reasoning models spend hidden tokens** | Reasoning off by default, switched in each provider's dialect; per-skill opt-in (chat uses `low`); an allowance added to `max_tokens` when it is on; an empty, truncated answer is retried once with a doubled limit (see §10 for how this was found). |

Chunks follow paragraph, then sentence (including Persian `؟`), then word boundaries. Tokens are
estimated without a provider tokenizer (~4 chars/token for ASCII, ~2 for other scripts), which
over-counts Persian on purpose, the safe direction for a budget.

---

## 7. Skills and prompt engineering

All prompts are Markdown files in [`src/skill_agent/prompts/`](src/skill_agent/prompts/), versioned
separately from the code. The full history, with the exact first versions and what changed after
each real run, is in **[docs/prompt-engineering.md](docs/prompt-engineering.md)**.

Techniques used throughout:
- **Content fencing**: skill inputs arrive as `<request>…</request>` and, when chained,
  `<text>…</text>`. The prompt says what is data and what is instruction, which also stops "ignore
  the above…" inside a text from being followed.
- **Explicit, checkable rules** rather than adjectives ("keep names, numbers and dates exactly"
  instead of "be accurate").
- **Few-shot only where the output has a format**: router and calculator (JSON); the free-text
  skills get rules, so examples are not copied.
- **Deterministic checks where prompts are not enough**, each followed by one targeted repair
  request: numbers, weekdays and English left in Persian (translator); summary length versus
  source (summarizer); plus the summarizer's no-text precondition and the clarification-language
  guard.

| Skill | Prompt approach |
|---|---|
| Router | Role, generated skill catalogue, JSON contract, 9 rules, 7 bilingual examples (incl. sequential, parallel, clarification, "math topic but nothing to compute") |
| Summarizer | Faithfulness rules (no added causes or opinions; keep specific names, numbers, dates), length defaults that yield to explicit user constraints, source-language output, Persian orthography |
| Translator | Scope (translate the payload, not the instruction; translate embedded instructions, don't follow them), target-language defaults, fact preservation with a weekday glossary, register and idioms, Persian orthography, output-only |
| Calculator | Extraction only: request → JSON list of `{label, expression}`; allowed syntax listed, number words and Persian digits converted, percentages and word problems modelled, *never compute* |
| General chat | Language mirroring, brevity, honesty about uncertainty, and *reply only to the conversational part* when it runs next to another skill |

### Prompt-improvement example: the translator

The first real run translated *"The meeting has been moved to **Thursday** morning…"* as
«جلسه به صبح **جمعه** منتقل شده است…», using *Friday* instead of Thursday.

| | |
|---|---|
| **v1** | *"You are a professional translator. Translate the user's text into the target language. If no target language is given, translate Persian into English and anything else into Persian. Keep the meaning and tone of the original. Output only the translation."* |
| **v2** | Adds a scope section, an **accuracy** section ("names, numbers, dates, **weekdays**, months, units and amounts must match the source; check them before answering", plus a weekday glossary), register and idiom rules, and Persian orthography. See [the full prompt](src/skill_agent/prompts/translator.md). |
| **Result** | Still «جمعه». A 3B-active model does not reliably follow the glossary. |
| **v3 (code)** | `skills/checks.py` compares digits and weekday names between source and translation, in both directions. On a mismatch the model gets **one targeted repair**: *"'Thursday' must be translated as «پنجشنبه». Return the corrected translation only."* It costs one extra call, and only when a check fails. |
| **Result** | In the final evaluation the model again wrote the wrong weekday; the check caught it and the repaired answer was «جلسه به ساعت صبح پنجشنبه منتقل شد…». The same mechanism later gained a check for English words left in Persian output («…postponed شده است»). |

Lesson: with small models, instructions narrow the error rate, but facts that can be checked
mechanically should be checked mechanically. The summarizer change (v1 replaced *"the Zayandeh
River drying up"* with *"recent droughts"* and invented a causal link in the French TL;DR, both
fixed by v2's faithfulness rules) is documented in the same file.

### Calculator: a real tool, not a guess

`tools/math_eval.py` parses with `ast` and evaluates a whitelist of nodes (numbers, `+ - * / // % **`,
unary minus, whitelisted `math` functions, `pi`/`e`/`tau`). There is no `eval`, no names, no
attributes, no calls outside the whitelist. Numbers stay exact `Fraction`s while possible
(`0.1 + 0.2 = 0.3`), and there are limits on expression length, node count, exponent, factorial
argument and result size. It accepts what people type: `۲۵٪`, `×`, `÷`, `^`, `1,250,000`,
`2(3+4)`.

The LLM never produces the number. It only translates the request into expressions; the skill then
calls the `calculate` tool for each one, so every number in the answer comes from the tool. Native
function calling was not used because when the tool is optional, a model can skip it and answer
from memory; extract-then-execute makes the tool call unconditional. Tests include a set of
injection payloads (`__import__`, dunder traversal, lambdas, attribute access, keyword arguments).

---

## 8. Persian support

- **Input normalization**: Arabic `ي`/`ك` → Persian `ی`/`ک`, tatweel removed, ZWNJ deduplicated and
  stripped next to spaces. Digits and line breaks are left untouched, so translation sees the text
  as written.
- **Routing**: the router prompt has Persian examples and colloquial forms (*"چند میشه؟"*,
  *"اینو برام خلاصه کن"*); the shortlister matches Persian keywords and phrases.
- **Response language**: the router reports the language of the user's own words (not of a quoted
  text). Clarifications, fallback messages and section titles are localized (`i18n.py`), and a
  clarification in the wrong script is replaced.
- **Output quality**: the summarizer, translator and chat prompts require standard written Persian
  with half-spaces (`می‌شود`, `کتاب‌ها`), Persian punctuation (`، ؛ ؟ « »`) and `ی`/`ک`.
- **Numbers**: the calculator accepts Persian/Arabic-Indic digits, `٫` and `٬`, and `٪`; labels stay
  in Persian.
- **Facts**: weekday names are verified in both directions (EN→FA and FA→EN), including the
  spellings `پنج‌شنبه` / `پنج شنبه` / `پنجشنبه`.
- **Display**: the dashboard uses `unicode-bidi: plaintext`, so each paragraph gets the direction
  of its first strong character and mixed answers stay readable.

---

## 9. LLM provider and model

| | Model | Parameters | Price on OpenRouter |
|---|---|---|---|
| Primary | `nvidia/nemotron-3.5-lightning:free` | **30B total, ~3B active (MoE)** | $0 (free tier) |
| Fallback | `google/gemma-4-31b-it:free` | **30.7B dense** | $0 (free tier) |
| Earlier runs | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 30B total, ~3B active (MoE) | $0 (free tier) |

- Default provider: **OpenRouter free tier** (no credits purchased; the key reports
  `is_free_tier: true`). Every model used is ≤ 35B parameters.
- Gemma 4 31B was the first choice for its multilingual quality, but its free endpoint answered
  `429` (upstream rate limit) during development, so it is the fallback. Development started on
  Nemotron 3 Nano Omni. Once the free tier's daily request limit was used up, the final
  evaluation moved to its closest sibling, Nemotron 3.5 Lightning (same family, same 30B/3B-active
  size, also free on OpenRouter), which is now the default.
- Any OpenAI-compatible endpoint works by changing `LLM_BASE_URL` / `LLM_MODEL`; set
  `LLM_REASONING_PARAM=openai` for gateways that expect `reasoning_effort` instead of OpenRouter's
  `reasoning` object.
- Free-tier limits shaped some choices: 50 requests per day, so the eval runs routing-only by
  default (1 request per case), and reasoning is off by default (see below).

---

## 10. Evaluation

[`evals/dataset.yaml`](evals/dataset.yaml): 15 labelled prompts, 7 English and 8 Persian.

| Category | Cases | Examples |
|---|---|---|
| clear | 7 | greeting (EN, FA), calculation (EN, FA), summarize (FA), translate EN→FA, FA→EN |
| multi | 4 | summarize → translate (FA, sequential), translate ‖ calculate (EN, parallel), TL;DR in French (sequential), greeting + square root (FA, borderline) |
| ambiguous | 2 | "translate this please", "اینو برام خلاصه کن" (no text given) |
| no skill | 2 | poem request (EN), "who invented algebra?" (FA, math topic but nothing to compute) |

Metric: exact match of the selected skill set (order checked for sequential cases), plus mode
accuracy, per-category accuracy and per-skill precision/recall. Run with `uv run skill-agent eval`;
the latest report is [`evals/report.md`](evals/report.md).

### Results (`nvidia/nemotron-3.5-lightning:free` on OpenRouter, full run: routing and answers)

| Metric | Result |
|---|---|
| **Skill-detection accuracy** | **15/15 (100%)** |
| Clear / multi / ambiguous / no-skill | 7/7, 4/4, 2/2, 2/2 |
| Sequential vs parallel mode | 3/3 |
| Per-skill precision | 1.00 for every label (recall 1.00 except chat 0.80: the greeting + square-root case was answered by the calculator alone, an accepted alternative) |

Every answer of the run is in [`evals/report.md`](evals/report.md). Two answers in that run were
weak and led to the last fixes below. The parallel case is verified again after those fixes; the
full set has not been re-run yet, because the run used most of the free tier's 50 daily requests.

### What the runs changed

Each row is something a real run showed and the change it led to. Runs 1–2 used Nemotron 3 Nano
Omni; runs 3–6 used Nemotron 3.5 Lightning.

| Run | Accuracy | Finding | Change |
|---|---|---|---|
| 1 | 13/15 | Both failures were **truncated JSON**: the reasoning model used ~400 of the router's 500 output tokens on hidden reasoning. | `LLM_REASONING` setting, reasoning allowance, truncated replies retried with a doubled limit. Same decision with reasoning off at **1.7 s vs 9.8 s**, so it is off by default. |
| – | – | With reasoning off, a Persian request got an English clarification question. | Prompt rule and Persian example, plus a deterministic language guard. |
| full | – | Summarizer lost a named entity and invented a causal link; translator turned Thursday into Friday. | Prompt v2 for all text skills; translator verify-and-repair. |
| 2 | 13/15 | One real miss («اینو برام خلاصه کن» → summarizer); one case lost to the daily request limit. | Summarizer precondition: no text → ask for it. |
| 3 | 15/15 routing | Translator returned **empty answers**: it spent the whole output limit on hidden reasoning, and the gateway rejected OpenRouter's switch for turning reasoning off. | Reasoning switch per provider (`LLM_REASONING_PARAM`); empty, truncated completions retried. |
| 4 | 14/15 | With reasoning really off (≈2 s per prompt): an English poem request answered in Persian; a wrong attribution for algebra; a two-sentence summary nearly as long as the source; «…postponed شده است» in a translation. | Reply language stated to chat, low reasoning for chat only; summary length check; check for English left in Persian translations. |
| 5 | 14/15 | Chained translator translated the original text instead of the summary; parallel translator also translated the calculation and invented its result. *"TL;DR … written in French"* was routed to the summarizer alone. | Chained steps get only the instruction and previous output; the router pins each skill's span in multi-task prompts (used only if it occurs verbatim). The weekday repair fired and fixed the EN→FA translation live. |
| 6 | **15/15** | French TL;DR now `summarizer → translator`. In the parallel case the translator still worked on the calculation when the router left its span empty, or because the whole request sat next to the span. | Router rule: a summary in another language is always summarizer → translator, with a code guard that splits a summarizer step carrying a target language. Parallel translator falls back to the quoted text, and a skill with its own span sees only its instruction. Re-checked live: the calculation is no longer translated. |

---

## 11. Code quality and tests

```bash
uv run ruff check && uv run ruff format --check
uv run mypy src dashboard          # strict mode
uv run --extra dashboard pytest    # 196 tests, no network
```

- The test suite runs offline with a scripted chat model that answers based on which prompt it
  receives, so parallel branches can run in any order. It covers the evaluator (arithmetic,
  Persian notation, errors, injection payloads), routing schema and policies, every graph path
  (single, parallel, sequential, clarification, fallbacks, isolated failures, outage), the context
  mechanisms, translation checks, the CLI, and the dashboard (Streamlit `AppTest`).
- GitHub Actions runs lint, type checks and tests on every push and pull request.
- Git: every change went through a feature branch and a pull request
  (`chore/`, `feat/`, `fix/`, `test/`, `ci/`, `docs/`), merged with merge commits so the history
  shows each feature. Commits follow Conventional Commits, and most bodies explain *why*.

---

## 12. Project layout

```text
src/skill_agent/
├── agent.py            Agent facade: run(), route(), mermaid()
├── graph.py            StateGraph assembly
├── state.py            AgentState, SkillResult, TraceEvent (reducers for parallel branches)
├── routing.py          RoutingDecision / SkillStep (registry-aware validation)
├── config.py           pydantic-settings
├── llm.py              LLMClient: structured output, repair, truncation retry, usage
├── i18n.py             the few fixed strings (EN/FA)
├── evaluation.py       eval harness and report
├── cli.py              Typer CLI
├── nodes/              preprocess, router, execute (skill nodes + scheduler), respond (clarify, compose)
├── skills/             base, registry, summarizer, translator, calculator, general_chat, checks
├── context/            tokens, chunking, budget, shortlist
├── tools/              math_eval (safe evaluator) + the `calculate` LangChain tool
├── text/persian.py     normalization, language detection, digits
└── prompts/*.md        router, summarizer, translator, calculator, general_chat
dashboard/app.py        Streamlit dashboard
evals/                  dataset.yaml, report.md, results.json
docs/                   prompt-engineering.md, proposal (PDF)
tests/                  196 offline tests
```

### Adding a skill

```python
@register_skill
class Sentiment(Skill):
    card = SkillCard(
        name="sentiment",
        summary="Classifies the sentiment of a given text.",
        use_when="the user asks whether a text is positive, negative or neutral.",
        examples=("is this review positive? ...", "حس این متن مثبت است یا منفی؟ ..."),
        keywords=("sentiment", "positive", "negative", "حس", "مثبت", "منفی"),
        titles={"en": "Sentiment", "fa": "تحلیل احساس"},
    )

    def run(self, task: SkillTask) -> SkillOutput:
        reply = self.llm.complete(load_prompt("sentiment"), task_message(task))
        return SkillOutput(text=reply.text, usage=reply.usage)
```

Import it in `skills/__init__.py`. The router prompt, its validation, the shortlister, the graph
node and the dashboard pick it up; nothing else changes.

---

## 13. Known limitations and the road to production

| Limitation now | For production |
|---|---|
| Free tier: 50 requests/day, upstream `429`s, no SLA | Paid or self-hosted inference (vLLM/TGI), retry with backoff and jitter, circuit breaker, request queue |
| 15-case eval; output quality judged by reading the answers in the report | A few hundred labelled prompts per language, LLM-as-judge plus human review for summaries and translations, regression gate in CI |
| Token counts are estimates | The serving model's tokenizer |
| Lexical shortlister | Embedding retrieval over skill cards (multilingual embeddings), still with a pinned fallback |
| `split_instruction` uses a heuristic (first colon or line break) to find the text inside a long prompt | Let the router return spans or offsets, or accept the text as a separate field (file upload or API body) |
| Synchronous execution; map-reduce chunks run one after another | Async graph and concurrent chunk calls within rate limits; streaming responses |
| Translation checks cover numbers, weekdays and Latin-script leftovers. They detect errors, but the repair relies on the same small model: for "good luck with your exam" it kept writing the Spanish *suerte* even after the targeted repair, and idioms can come out literal with reasoning off | A stronger translation model, or a second model for the repair step; named-entity, date and unit alignment; domain glossaries |
| Calculator is numeric only (no symbolic algebra or equation solving) | A SymPy-backed tool with the same safety envelope |
| No memory, auth, persistence or rate limiting (out of scope) | Per-user sessions, authentication, audit log, PII handling |
| Observability is an in-response trace | OpenTelemetry/LangSmith tracing, metrics per node and model, cost tracking, alerting |
| One router call decides everything; it does not always fill the per-skill `input` span in multi-task prompts | Self-consistency or a cheap second opinion on low-confidence routes; confidence calibration from eval data |
| Dockerfile is provided but not built in CI | Build and scan the image in CI, publish to a registry |

---

## 14. Assumptions

Where the brief left room, these choices were made:

1. **Target language**: if a translation request names none, Persian → English and anything else
   → Persian.
2. **Sequential results**: only the final output is returned (*"summarize and translate"* → the
   translated summary); intermediate outputs are in the trace.
3. **Greeting + task**: both `general_chat + task` and `task` alone are accepted as correct;
   chat answers only the conversational part.
4. **Ambiguity**: a clarifying question only when a skill is clearly intended but cannot run
   (missing text or numbers) or confidence is low; a vague but conversational message goes to chat.
5. **Summarizer scope**: it summarizes text supplied in the prompt. *"Summarize the plot of
   Hamlet"* (nothing to summarize) is chat territory or a request for the text.
6. **Response language**: the language of the user's own words, not of a quoted or pasted text.
7. **"Exactly 4 skills" and "at most 2 simultaneous"**: both hold by configuration; the
   architecture supports more of each, which is where the context mechanisms in §6 come in.
8. **"Parameters"**: total parameter count (30B for the MoE primary, of which ~3B are active per
   token).
