# Design notes

Details that would make the README too long: the full configuration, how routing output is checked,
the context mechanisms in depth, how to add a skill, and what each evaluation run changed.

## Configuration

Everything is read from the environment or `.env` ([`.env.example`](../.env.example) lists all of it).

| Variable | Default | What it does |
|---|---|---|
| `LLM_API_KEY` (or `OPENROUTER_API_KEY`) | | Provider key, the only required setting |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint works |
| `LLM_MODEL` | `nvidia/nemotron-3.5-lightning:free` | Main model |
| `LLM_FALLBACK_MODEL` | `google/gemma-4-31b-it:free` | Tried when the main model fails |
| `LLM_REASONING` | `off` | Hidden reasoning (`off`, `low`, `medium`, `high`) |
| `LLM_REASONING_PARAM` | `openrouter` | How that switch is sent: `openrouter`, `openai` (`reasoning_effort`) or `none` |
| `MAX_SKILLS_PER_REQUEST` | `2` | Skills per prompt |
| `CLARIFY_BELOW_CONFIDENCE` | `0.4` | Below this the agent asks instead of guessing |
| `SHORTLIST_THRESHOLD`, `SHORTLIST_TOP_K` | `8`, `6` | When and how much the router's skill list is trimmed |
| `CONTEXT_WINDOW` | `16000` | Window every call has to fit in (estimated tokens) |
| `MAX_OUTPUT_TOKENS`, `TOTAL_OUTPUT_BUDGET` | `1200`, `2000` | Per-step cap and the budget shared by parallel steps |
| `ROUTER_EXCERPT_TOKENS`, `CHUNK_TOKENS` | `700`, `2500` | How much of a long message the router reads; chunk size for long texts |
| `DASHBOARD_PASSWORD` | | Optional sign-in screen for a hosted dashboard |

Chat always uses a little reasoning, and so do calculator requests that look like story problems;
everything else follows `LLM_REASONING`.

## How the routing output is checked

`routing.py` cleans the decision before anything runs. Loose skill names are mapped (`"Translate"`
becomes `translator`, `"chat"` becomes `general_chat`), unknown names are rejected, there can't be more
than `MAX_SKILLS_PER_REQUEST` skills, the mode is made consistent with the number of skills, and
language names become codes. Validation runs against the live registry through Pydantic's validation
context, so the schema doesn't change when a skill is added.

When something is wrong, the error is written for the model ("unknown skill name(s) ['poet']; use
only: summarizer, …") and it gets one chance to fix its answer. A reply cut off by the token limit is
retried with a larger limit. If it is still unusable, the request goes to `general_chat` with
confidence 0.

## Context mechanisms in depth

- **Shortlist.** Above `SHORTLIST_THRESHOLD` skills, a lexical scorer (keyword phrases plus
  IDF-weighted word overlap, both languages, no model call) keeps the `SHORTLIST_TOP_K` most relevant
  cards and always the fallback. Tests register 10, 50 and 200 skills and check the router prompt stays
  the same size, and check the right skill survives in a 54-skill catalogue.
- **Long messages.** The router reads the head and tail of a long message; the request is almost
  always there, and the middle is the document itself.
- **Budgets.** Parallel steps share `TOTAL_OUTPUT_BUDGET`; each step in a chain is capped at
  `MAX_OUTPUT_TOKENS`, so the next step's input is bounded.
- **Chains.** The next step gets the previous output and the user's instruction, never the original
  text, the state or any history.
- **Texts larger than the window.** Summaries use map-reduce, merging again while the partial
  summaries are too long; a test runs this against a tiny window and checks every call fits.
  Translations go chunk by chunk. Chunks split on paragraphs, then sentences (Persian `؟` included),
  then words.
- **Token estimates.** About 4 characters per token for ASCII and 2 for other scripts. That
  over-counts Persian on purpose, the safe direction for a budget.
- **Hidden reasoning.** When it's on, an allowance is added to `max_tokens`, and an answer that comes
  back empty because the limit was used up is retried once with a bigger limit.

## Adding a skill

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

Import it in `skills/__init__.py`. The router prompt, the validation, the shortlist, the graph and the
dashboard all pick it up.

## What each evaluation run changed

Runs 1 and 2 used Nemotron 3 Nano Omni; runs 3 to 7 used Nemotron 3.5 Lightning.

| Run | Score | What went wrong | What I changed |
|---|---|---|---|
| 1 | 13/15 | Cut-off JSON: the model spent most of the router's 500 tokens on hidden reasoning. A Persian request got its clarifying question in English. The translator turned Thursday into Friday; the summarizer invented a cause. | Reasoning made configurable and off by default (1.7 s instead of 9.8 s, same decisions), cut-off replies retried; a language check on clarifications; second version of the text-skill prompts and the translator's check-and-correct step. |
| 2 | 13/15 | «اینو برام خلاصه کن» went to the summarizer; one case hit the daily limit. | The summarizer asks for the text when there isn't any. |
| 3 | 15/15 | The translator returned empty answers: the endpoint ignored OpenRouter's switch for turning reasoning off. | The switch is sent in whichever form the provider expects; empty cut-off answers are retried. |
| 4 | 14/15 | A poem request answered in Persian, a wrong name for the algebra question, a summary nearly as long as the text, «…postponed شده است» in a translation. | Chat is told the reply language and reasons a little; summaries get a length check; translations are checked for leftover English. |
| 5 | 14/15 | In a chain the translator translated the original text; in the parallel case it translated the calculation too. The French TL;DR went to the summarizer alone. | Chained steps only get the instruction and the previous output; the router can pin each skill's span. |
| 6 | 15/15 | The parallel translator still sometimes saw the calculation. | A summary in another language is always two skills; the parallel translator falls back to the quoted text. |
| 7 | 15/15 | Found by using the dashboard: overlapping spans, a correction repeating its mistake, a story problem with a wrong sign, math displayed back to front in Persian answers. | Overlapping spans are cut apart; corrections are re-checked with one warmer retry; story problems get a little reasoning; code spans are laid out left to right. |

Run 7 used the same model through another OpenAI-compatible gateway, because the free tier's daily
limit was used up; the committed report is run 6 on OpenRouter.
