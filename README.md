# Skill Agent

[![CI](https://github.com/mhmdjgh/I4TWiNS/actions/workflows/ci.yml/badge.svg)](https://github.com/mhmdjgh/I4TWiNS/actions/workflows/ci.yml)

A small multi-skill agent built on LangGraph. You give it a free-form prompt in English or Persian,
it works out which skill (or two) the request needs, runs them and sends back one answer.

There are four skills:

- **summarizer** shortens a text you give it. Texts that don't fit the context window are handled
  with map-reduce.
- **translator** translates between Persian, English and other languages, and double-checks
  numbers and weekdays afterwards.
- **calculator** never lets the model do arithmetic. The model only writes the expression; a safe
  evaluator exposed as the LangChain tool `calculate` computes it.
- **general_chat** handles greetings, small talk and general questions, and catches anything that
  doesn't fit the other three.

A prompt can use up to two skills. They run in parallel when the tasks are independent, or one after
the other when the second needs the first one's output. The main interface is a CLI; there is also a
Streamlit dashboard that shows what happened inside each request.

Here is a real run (CLI output trimmed):

```text
$ skill-agent ask "متن زیر را خلاصه کن و بعد خلاصه‌اش را به انگلیسی ترجمه کن: شهر اصفهان با پل‌های تاریخی، ..."
routing  summarizer -> translator (sequential)
answer   Isfahan, with its historic bridges, Naqsh-e Jahan Square, and Safavid architecture, is one
         of Iran's top tourist destinations, attracting thousands of domestic and international
         visitors annually, while the recent drying up of the Zayandeh River has damaged the city's
         appearance and tourism-related businesses.
```

## Contents

1. [Running it](#1-running-it)
2. [Architecture](#2-architecture)
3. [Routing](#3-routing)
4. [Requests that need two skills](#4-requests-that-need-two-skills)
5. [Fallback behaviour](#5-fallback-behaviour)
6. [Keeping the context window under control](#6-keeping-the-context-window-under-control)
7. [Skills and prompts](#7-skills-and-prompts)
8. [Persian](#8-persian)
9. [Model and provider](#9-model-and-provider)
10. [Evaluation](#10-evaluation)
11. [Tests and code quality](#11-tests-and-code-quality)
12. [Project layout](#12-project-layout)
13. [Limitations and what production would need](#13-limitations-and-what-production-would-need)
14. [Assumptions](#14-assumptions)

## 1. Running it

You need Python 3.11+, [uv](https://docs.astral.sh/uv/) and a free
[OpenRouter](https://openrouter.ai/keys) key. No credit is needed for the free models.

```bash
git clone https://github.com/mhmdjgh/I4TWiNS.git
cd I4TWiNS
uv sync
cp .env.example .env    # then put your key in LLM_API_KEY
```

### Configuration

The only required variable is `LLM_API_KEY`. The rest have sensible defaults, listed in
[`.env.example`](.env.example). The ones you are most likely to touch:

| Variable | Default | What it does |
|---|---|---|
| `LLM_API_KEY` (or `OPENROUTER_API_KEY`) | | Provider key |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint works |
| `LLM_MODEL` | `nvidia/nemotron-3.5-lightning:free` | Main model |
| `LLM_FALLBACK_MODEL` | `google/gemma-4-31b-it:free` | Tried when the main model fails |
| `LLM_REASONING` | `off` | Hidden reasoning (`off`, `low`, `medium`, `high`). Chat always uses `low` |
| `LLM_REASONING_PARAM` | `openrouter` | How that switch is sent: `openrouter`, `openai` (`reasoning_effort`) or `none` |
| `MAX_SKILLS_PER_REQUEST` | `2` | Skills per prompt |
| `CLARIFY_BELOW_CONFIDENCE` | `0.4` | Below this the agent asks instead of guessing |
| `SHORTLIST_THRESHOLD`, `SHORTLIST_TOP_K` | `8`, `6` | When and how much the router's skill list is trimmed |

The context-budget numbers (`CONTEXT_WINDOW`, `MAX_OUTPUT_TOKENS`, `TOTAL_OUTPUT_BUDGET`,
`ROUTER_EXCERPT_TOKENS`, `CHUNK_TOKENS`) are explained in [section 6](#6-keeping-the-context-window-under-control).

### CLI

```bash
uv run skill-agent ask "What is (17.5 * 42) / 3 + 2^10?"   # answer, routing decision and trace
uv run skill-agent ask "سلام! حالت چطوره؟" --json           # the whole response as JSON
uv run skill-agent chat                                    # interactive loop (no memory between turns)
uv run skill-agent route "translate this please"           # only the routing decision
uv run skill-agent eval                                    # routing accuracy on evals/dataset.yaml
uv run skill-agent skills                                  # also: config, graph
```

Windows terminals print Persian in logical order, so it can look reversed there. The dashboard
shows it properly.

### Dashboard

```bash
uv run --extra dashboard streamlit run dashboard/app.py
```

It is optional and talks to the agent directly, in the same process. The brief asked for a CLI and
said not to build a web API, so there is no API layer behind it. It has three pages:

- **Assistant**: a chat view. Under each answer there is one line with the skills used, the mode and
  the time, and a "Behind the scenes" panel with every step (time and tokens), the routing decision,
  tool calls and the raw JSON.
- **How it works**: the request lifecycle, the graph, the skill cards and the context settings.
- **Evaluation**: the latest results, per category and per skill, and every case with its answer.
  Re-running from here saves to `evals/runs/` and leaves the committed results alone.

The layout works on phones too. The interface is in English; prompts and answers can be in either
language, and Persian answers are laid out right to left.

### Docker

```bash
docker build -t skill-agent .
docker run --rm -p 8501:8501 --env-file .env skill-agent              # dashboard
docker run --rm -it --env-file .env skill-agent skill-agent chat      # CLI
```

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

`preprocess` cleans up Persian text (Arabic ي/ك become ی/ک, stray half-spaces are fixed) and makes
a first guess at the language. `router` is the only node that always calls the model: it returns a
JSON decision that is validated with Pydantic. Each skill has its own node, generated from a
registry. `clarify` and `compose` are plain code: one returns the clarifying question, the other
puts the results together.

A few decisions shaped the rest of the code:

**Skills are plugins.** Every skill registers itself with `@register_skill`. The router prompt, the
validation of the router's answer and the graph nodes are all built from that registry, so adding a
skill is one new module and the graph doesn't change.

**The router reads short cards, not prompts.** Each skill has a card of about three lines: what it
does, when to use it, a few examples. The full system prompt of a skill is only loaded inside its own
node. That keeps routing cheap as the number of skills grows.

**JSON plus Pydantic instead of native tool calling.** Free models are inconsistent about function
calling. Asking for JSON and validating it works on any OpenAI-compatible endpoint, and when
validation fails the error goes back to the model for one more try.

**Validation against the live registry.** Instead of a hard-coded `Literal` of skill names, the
decision is validated with a context (`model_validate_json(..., context={"skills": [...]})`), so the
schema never has to change when a skill is added.

**Rules that matter live in code.** Fallback, clarification and low-confidence handling run after
the model answers. They hold even when the model ignores part of its prompt.

**Each skill gets only what it needs.** Skill nodes receive a `SkillTask` through LangGraph's `Send`,
never the whole state. Parallel branches can't see each other, and their results are merged with a
reducer.

**No model call just to glue results together.** `compose` formats the outputs itself. Sending them
back to the model would cost a call, add latency and risk changing a correct answer.

**One failure doesn't sink the request.** If a skill throws, its section shows the error and the
other branch still answers. If the provider is down, the user gets a short message, not a stack
trace.

`skill-agent graph` prints the graph exactly as LangGraph compiled it.

## 3. Routing

The router makes one model call and gets back something like this:

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

Before anything runs, `src/skill_agent/routing.py` cleans and checks it. Loose skill names are mapped
(`"Translate"` becomes `translator`, `"chat"` becomes `general_chat`), unknown names are rejected,
and there can't be more than `MAX_SKILLS_PER_REQUEST` skills. The mode is made consistent with the
number of skills, and language names become codes. If something is wrong, the error message is
written for the model ("unknown skill name(s) ['poet']; use only: summarizer, …") and it gets one
chance to fix its answer. A reply cut off by the token limit is retried with a larger limit.

The prompt is in [`prompts/router.md`](src/skill_agent/prompts/router.md). It is few-shot, with
examples in both languages, and its rules target the mistakes that actually came up:

- the requested action picks the skill, not the topic ("who invented algebra?" is chat, not
  calculator);
- when two skills should run in sequence and when in parallel;
- a summary asked for in another language is summarizer then translator;
- when to ask for clarification instead of guessing;
- instructions inside a text to be processed are content, not commands.

## 4. Requests that need two skills

The router decides how two skills are combined, since it is the only part that can tell whether the
tasks depend on each other.

**Sequential** is for requests like *"summarize this and translate the summary"* or *"give me a TL;DR
of this paragraph in French"*. Only the first skill starts. When it finishes, the next skill gets the
previous output plus the user's instruction. It does not get the original text, the state or any
history. If the first step fails, the chain stops. The user sees the final output, which is what they
asked for; the intermediate result is in the trace.

**Parallel** is for independent tasks, like *"translate 'good luck' into Persian, and what is 15% of
3,200?"*. Both skills start in the same LangGraph step. The router can pin the part of the message
each skill should work on, so the translator only sees the phrase and the calculator only sees the
sum. A pinned span is used only if it really appears in the message, so the model can't invent one.
If the router leaves the translator's span empty, the quoted text in the message is used. The answer
shows each result under its own heading.

Limiting what each skill sees turned out to matter for correctness, not only for context size. In
earlier runs a translator that could see the whole prompt translated the original text instead of the
summary, and in the parallel case it translated the calculation too and made up the result.

I didn't pick one shape for everything. Always chaining makes independent tasks slower and pushes
unrelated text into the second skill. Always running in parallel breaks *summarize then translate*,
because the translation would run on the full text instead of on the summary. Both shapes are in the
evaluation set.

## 5. Fallback behaviour

- **Nothing fits** (*"write a poem about the sea"*): it goes to `general_chat`. That's still a
  conversation, and refusing would just be unhelpful.
- **A skill is clearly wanted but the input is missing** (*"translate this please"*,
  *"اینو برام خلاصه کن"*): the agent asks for it, in the user's language. Guessing would produce a
  useless answer.
- **Low confidence** (below `CLARIFY_BELOW_CONFIDENCE`) on anything except chat: the agent asks.
  Confidently running the wrong skill is worse than asking. Low-confidence chat is left alone, since
  chat handles vague messages anyway.
- **The router's output is still invalid after the retry**: the request goes to `general_chat` with
  confidence 0, and the trace says why.
- **The summarizer gets almost no text** (under 8 words): it asks for the text. This is a second line
  of defence for a routing mistake seen during evaluation.
- **A skill fails** (timeout, provider error): that skill's section shows the error and the other one
  still answers.
- **The provider is unreachable or rate limited**: a short "model not reachable" message, with the
  error kept in the response.

There is one more small guard: if the model writes a clarifying question in the wrong language, which
happened once with a Persian request, it is replaced with a fixed question in the right language.

## 6. Keeping the context window under control

This was the main design problem: as more skills are added and more of them run per request, every
call still has to fit in the model's window. Each way the context can grow has its own fix, in
`src/skill_agent/context/`.

**More skills.** The router only reads compact cards. Above `SHORTLIST_THRESHOLD` skills, a cheap
lexical shortlister (keyword phrases and IDF-weighted word overlap, in both languages, no model call)
keeps the `SHORTLIST_TOP_K` most relevant cards, plus the fallback. A test registers 10, 50 and 200
skills and checks that the router prompt stays the same size; another checks that the right skill
survives the shortlist in a 54-skill catalogue, for English and Persian prompts.

**Long messages.** The router reads only the beginning and the end of a long message. The request is
almost always there; the long middle is the document itself, which routing doesn't need.

**Several skills in one answer.** Parallel steps share `TOTAL_OUTPUT_BUDGET`. In a chain, every
intermediate output is capped at `MAX_OUTPUT_TOKENS`, so the next step's input is bounded by
construction.

**History piling up in a chain.** The next step only receives the previous output and the
instruction. Parallel branches are isolated and only see their own span.

**Texts larger than the window.** Summaries use map-reduce: split, summarize each part, then merge,
repeating the merge while the partial summaries are still too long. A test runs this against a
deliberately tiny window and checks that every call fits. Translations go chunk by chunk and are
joined in order. Chat and the calculator trim their input to whatever room is left.

**Hidden reasoning.** Reasoning models spend tokens thinking before they answer. Reasoning is off by
default (section 10 explains why), chat opts into a little of it, an allowance is added to
`max_tokens` whenever it's on, and an answer that comes back empty because the limit was used up is
retried once with a bigger limit.

Chunks split on paragraphs first, then sentences (Persian `؟` included), then words. Token counts are
estimated without the provider's tokenizer, at roughly 4 characters per token for ASCII and 2 for
other scripts. That over-counts Persian on purpose, which is the safe direction for a budget.

## 7. Skills and prompts

The prompts live as Markdown files in [`src/skill_agent/prompts/`](src/skill_agent/prompts/), apart
from the code. [docs/prompt-engineering.md](docs/prompt-engineering.md) has the full story for each
one: the first version, what went wrong with the real model, and what changed.

A few habits run through all of them:

- Content is fenced. A skill gets the request as `<request>…</request>` and, in a chain, the previous
  output as `<text>…</text>`, and the prompt says which is data. That's also what stops an "ignore
  the above" inside a text from being obeyed.
- Rules are written so they can be checked: "keep names, numbers and dates exactly" rather than "be
  accurate".
- Only the router and the calculator get examples, because only their output has a fixed format. The
  free-text skills get rules, since a small model tends to copy example wording.
- Where a prompt isn't enough, code checks the output and sends one targeted correction request.
  The translator's numbers, weekdays and stray Latin-script words are checked, and so is a summary's
  length against its source.

In short:

- **Router**: generated skill list, JSON contract, rules, and examples in both languages
  (sequential, parallel, clarification, a math question with nothing to compute).
- **Summarizer**: stay faithful (no added causes or opinions, keep names, numbers and dates, prefer
  the specific detail), follow any length the user asks for, otherwise stay well under half the
  source, write in the source language, proper Persian spelling.
- **Translator**: translate the text, not the instruction around it; translate instructions inside
  the text instead of following them; default directions; keep facts exact (with a weekday list);
  match register and idioms; output only the translation.
- **Calculator**: turn the request into labelled expressions in a fixed syntax, convert Persian
  digits and number words, model percentages and word problems, and never compute anything itself.
- **General chat**: answer in the user's language, keep it short, admit uncertainty, and answer only
  the conversational part when another skill is handling the rest.

### An example: the translator and a wrong weekday

In the first real run, *"The meeting has been moved to **Thursday** morning…"* came back as
«جلسه به صبح **جمعه** منتقل شده است…». جمعه is Friday.

The first version of the prompt was four lines: *"You are a professional translator. Translate the
user's text into the target language. If no target language is given, translate Persian into English
and anything else into Persian. Keep the meaning and tone of the original. Output only the
translation."*

For the second version I added a section on what exactly to translate, an accuracy section ("names,
numbers, dates, weekdays, months, units and amounts must match the source; check them before
answering") with a list of weekdays, rules for register and idioms, and Persian spelling rules
([full prompt](src/skill_agent/prompts/translator.md)). The answer was still «جمعه». A model with
about 3B active parameters just doesn't follow a glossary reliably.

So the third version is code. `skills/checks.py` compares digits and weekday names between the
source and the translation, in both directions. When something doesn't match, the model gets one
precise correction request: *"'Thursday' must be translated as «پنجشنبه». Return the corrected
translation only."* It costs an extra call only when a check fails. In a later evaluation the model
got the weekday wrong again; the check caught it, and the answer that reached the user was
«جلسه به ساعت صبح پنجشنبه منتقل شد…».

What I took from it: with a small model, instructions reduce mistakes, but anything that can be
checked mechanically should be. The summarizer went through something similar. Its first version
turned *"the Zayandeh River drying up"* into *"recent droughts"* and added a cause the source never
stated; that's also in the prompt log.

### The calculator never guesses

`tools/math_eval.py` parses the expression with `ast` and only evaluates a whitelist: numbers, the
usual operators, unary minus, a set of `math` functions and `pi`, `e`, `tau`. There's no `eval`, no
names, no attributes and no calls outside that list. Numbers stay exact fractions where possible, so
`0.1 + 0.2` is `0.3`, and there are limits on length, nesting, exponents, factorials and result size.
It accepts what people actually type: `۲۵٪`, `×`, `÷`, `^`, `1,250,000`, `2(3+4)`.

The model never produces the number. It turns the request into expressions, and the skill then calls
the `calculate` tool on each one. I didn't use native function calling because when calling the tool
is optional, a model can skip it and answer from memory; this way the tool always runs. The tests
include a set of injection attempts (`__import__`, dunder tricks, lambdas, attribute access, keyword
arguments).

## 8. Persian

- **Input**: Arabic ي and ك become Persian ی and ک, tatweel is removed, and half-spaces (ZWNJ) are
  tidied. Digits and line breaks are left as they are, so the translator sees the text as written.
- **Routing**: the router prompt has Persian examples, including colloquial ones like
  «چند میشه؟» and «اینو برام خلاصه کن», and the shortlister matches Persian keywords.
- **Reply language**: the router reports the language of the user's own words, not of a quoted text.
  Clarifications, error messages and section titles come in that language, and a clarification in the
  wrong script is replaced.
- **Writing**: the summarizer, translator and chat prompts ask for standard written Persian, with
  half-spaces (می‌شود، کتاب‌ها), Persian punctuation and ی/ک.
- **Numbers**: the calculator takes Persian and Arabic-Indic digits, `٫`, `٬` and `٪`, and keeps the
  labels in Persian.
- **Weekdays**: checked in both directions, accepting پنج‌شنبه, پنج شنبه and پنجشنبه.
- **Display**: the dashboard gives each paragraph the direction of its first letter, so mixed answers
  read correctly.

## 9. Model and provider

| | Model | Parameters | Price |
|---|---|---|---|
| Main | `nvidia/nemotron-3.5-lightning:free` | 30B total, about 3B active (MoE) | free on OpenRouter |
| Fallback | `google/gemma-4-31b-it:free` | 30.7B dense | free on OpenRouter |
| Earlier runs | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 30B total, about 3B active (MoE) | free on OpenRouter |

Everything runs on OpenRouter's free tier: no credit was bought, and the key reports
`is_free_tier: true`. Every model listed is under the 35B limit.

I started with Gemma 4 31B because it's strong in Persian, but its free endpoint kept answering
`429` during development, so it became the fallback. Development then moved to Nemotron 3 Nano Omni,
and the final evaluation to Nemotron 3.5 Lightning, its close relative of the same size, which is now
the default.

Any OpenAI-compatible endpoint works by changing `LLM_BASE_URL` and `LLM_MODEL`. Some gateways expect
`reasoning_effort` instead of OpenRouter's `reasoning` object; `LLM_REASONING_PARAM=openai` covers
that.

The free tier allows 50 requests a day. That's why `skill-agent eval` checks routing only by default
(one request per case), and it's one of the reasons reasoning is off.

## 10. Evaluation

[`evals/dataset.yaml`](evals/dataset.yaml) has 15 labelled prompts, 7 in English and 8 in Persian:

- **7 clear**: a greeting in each language, a calculation in each language, a Persian summary, and a
  translation each way.
- **4 multi-skill**: summarize then translate (Persian, sequential), translate plus calculate
  (English, parallel), a TL;DR in French (sequential), and a greeting plus a square root (Persian,
  borderline).
- **2 ambiguous**: "translate this please" and «اینو برام خلاصه کن», neither with any text.
- **2 with no matching skill**: a poem request, and «چه کسی جبر را ابداع کرد؟», a question about
  math with nothing to compute.

A case counts as correct when the selected skills match exactly, in order for sequential cases. The
report also gives mode accuracy, per-category results and per-skill precision and recall. Run it with
`uv run skill-agent eval`; the latest report is [`evals/report.md`](evals/report.md).

### Results

Full run on OpenRouter with `nvidia/nemotron-3.5-lightning:free`, covering both routing and answers:

| | |
|---|---|
| Skill detection | **15/15 (100%)** |
| Clear / multi-skill / ambiguous / no skill | 7/7, 4/4, 2/2, 2/2 |
| Sequential vs parallel | 3/3 |
| Per skill | precision 1.00 everywhere; recall 1.00 except chat (0.80), because the greeting plus square-root case was answered by the calculator alone, which the dataset accepts |

All the answers are in [`evals/report.md`](evals/report.md). Two of them were weak and led to the last
fixes in the table below. I checked the parallel case again live after those fixes, but haven't
re-run the whole set, because that run used most of the day's free requests.

### What each run taught me

Runs 1 and 2 used Nemotron 3 Nano Omni; runs 3 to 6 used Nemotron 3.5 Lightning.

| Run | Score | What went wrong | What I changed |
|---|---|---|---|
| 1 | 13/15 | Both failures were cut-off JSON: the model spent about 400 of the router's 500 output tokens on hidden reasoning. | Made reasoning configurable, added an allowance for it, and retried cut-off replies with a larger limit. With reasoning off the router made the same decision in 1.7 s instead of 9.8 s, so off became the default. |
| | | With reasoning off, a Persian request got its clarifying question in English. | A prompt rule with a Persian example, plus a code check on the question's language. |
| | | Reading the answers: the summarizer dropped a named place and invented a cause; the translator turned Thursday into Friday. | Second version of the text-skill prompts, and the translator's check-and-correct step. |
| 2 | 13/15 | «اینو برام خلاصه کن» went to the summarizer; one case hit the daily request limit. | The summarizer now asks for the text when there isn't any. |
| 3 | 15/15 | Routing was perfect, but the translator returned empty answers: it used its whole output limit thinking, and that endpoint didn't accept OpenRouter's switch for turning reasoning off. | The reasoning switch is now sent in whichever form the provider expects, and empty, cut-off answers are retried. |
| 4 | 14/15 | With reasoning really off, things got faster (about 2 s a prompt) but: an English poem request was answered in Persian, the algebra question got a wrong name, a two-sentence summary was nearly as long as the text, and «…postponed شده است» appeared in a translation. | Chat is told the reply language and uses a little reasoning; summaries get a length check; translations are checked for leftover English. |
| 5 | 14/15 | In a chain the translator translated the original text instead of the summary; in the parallel case it translated the calculation too and invented the result. The French TL;DR went to the summarizer alone. | Chained steps only get the instruction and the previous output; the router can pin each skill's span. |
| 6 | **15/15** | The French TL;DR is now summarizer then translator. In the parallel case the translator still sometimes saw the calculation. | A rule that a summary in another language is two skills, with a code guard behind it. The parallel translator falls back to the quoted text and only sees its own instruction. |

## 11. Tests and code quality

```bash
uv run ruff check && uv run ruff format --check
uv run mypy src dashboard          # strict
uv run --extra dashboard pytest    # 196 tests, no network needed
```

The tests run offline against a scripted chat model that answers according to which prompt it
receives, so parallel branches can finish in any order. They cover the evaluator (arithmetic, Persian
notation, errors, injection attempts), the routing schema and its rules, every path through the graph
(single, parallel, sequential, clarification, fallbacks, a failing skill, a provider outage), the
context mechanisms, the translation checks, the CLI and the dashboard (with Streamlit's `AppTest`).
GitHub Actions runs lint, type checks and tests on every push and pull request.

Every change went through its own branch and pull request (`feat/`, `fix/`, `test/`, `docs/`, `ci/`,
`chore/`) and was merged with a merge commit, so the history reads feature by feature. Commit messages
follow Conventional Commits and the body usually says why the change was needed.

## 12. Project layout

```text
src/skill_agent/
├── agent.py            Agent: run(), route(), mermaid()
├── graph.py            builds the StateGraph
├── state.py            AgentState, SkillResult, TraceEvent
├── routing.py          RoutingDecision and SkillStep, validated against the registry
├── config.py           settings
├── llm.py              chat client: structured output, retries, token usage
├── i18n.py             the few fixed strings, in English and Persian
├── evaluation.py       evaluation runner and report
├── cli.py              command line
├── nodes/              preprocess, router, skill execution and scheduling, clarify and compose
├── skills/             registry, the four skills, translation checks
├── context/            token estimates, chunking, budgets, shortlist
├── tools/              the safe evaluator and the `calculate` tool
├── text/persian.py     normalization, language detection, digits
└── prompts/*.md        one prompt per skill, plus the router's
dashboard/              Streamlit app
evals/                  dataset.yaml, report.md, results.json
docs/                   prompt-engineering.md, proposal (PDF)
tests/
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

Import it in `skills/__init__.py` and that's it: the router prompt, the validation, the shortlist,
the graph and the dashboard all pick it up.

## 13. Limitations and what production would need

- **Free tier.** 50 requests a day, occasional `429`s, no guarantees. Production would need paid or
  self-hosted inference (vLLM, TGI) with retries, backoff and a circuit breaker.
- **A small evaluation.** 15 cases, and answer quality judged by reading them. A real setup needs
  hundreds of labelled prompts per language, an LLM judge plus human review for summaries and
  translations, and a regression gate in CI.
- **Estimated token counts.** They should come from the serving model's tokenizer.
- **Lexical shortlist.** Fine for a few dozen skills; beyond that, embedding search over the cards
  (still keeping the fallback).
- **Finding the text inside a long prompt** relies on a heuristic (the first colon or line break).
  Better: let the router return offsets, or take the text as a separate input.
- **Everything is synchronous**, and map-reduce chunks run one after another. An async graph with
  concurrent chunks and streaming would be faster.
- **Translation checks catch, but can't always fix.** They cover numbers, weekdays and stray
  Latin-script words, but the correction is done by the same small model. For "good luck with your
  exam" it kept writing the Spanish *suerte* even after being told exactly what was wrong, and with
  reasoning off idioms can come out literal. A stronger translation model, or a different model for
  the correction step, would fix most of this.
- **The calculator is numeric only.** Algebra and equation solving would need something like SymPy
  inside the same safety limits.
- **No memory, accounts or storage.** All out of scope here; production would need sessions,
  authentication, audit logs and care with personal data.
- **Observability is the trace in each response.** Production would want proper tracing
  (OpenTelemetry or LangSmith), per-node metrics and cost tracking.
- **One router call decides everything,** and it doesn't always fill in each skill's span in
  multi-task prompts. A second opinion on low-confidence routes and confidence calibrated on real
  data would help.
- **The Dockerfile isn't built in CI.** It should be built, scanned and published there.

## 14. Assumptions

Where the brief left room, this is what I assumed:

1. If a translation request doesn't name a language, Persian goes to English and anything else to
   Persian.
2. For two chained skills, the user gets the final output (for "summarize and translate", the
   translated summary). The intermediate step is in the trace.
3. For a greeting plus a task, both "chat + task" and "task alone" count as correct, and chat only
   answers the greeting.
4. The agent only asks for clarification when a skill is clearly wanted but can't run (no text, no
   numbers) or when confidence is low. A vague but conversational message goes to chat.
5. The summarizer summarizes text that's in the prompt. "Summarize the plot of Hamlet", with nothing
   to summarize, is a chat question or a request for the text.
6. Replies follow the language of the user's own words, not of a quoted or pasted text.
7. "Exactly four skills" and "at most two at once" hold by configuration. The design supports more of
   both, which is what section 6 is about.
8. "Parameters" means total parameters: 30B for the main model, of which about 3B are active per
   token.
