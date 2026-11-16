from __future__ import annotations

from skill_agent.context.chunking import chunk_text, split_instruction
from skill_agent.context.tokens import estimate_tokens
from skill_agent.i18n import t
from skill_agent.llm import Usage
from skill_agent.prompts import load_prompt
from skill_agent.skills.base import Skill, SkillCard, SkillOutput, SkillTask, task_message
from skill_agent.skills.registry import register_skill

_MAX_REDUCE_ROUNDS = 3
_MIN_WORDS = 8  # anything shorter is not worth summarizing; most likely the text is missing
_CHECK_FROM_WORDS = 40  # below this a summary may legitimately be close to the source length
_MAX_RATIO = 0.6  # a summary longer than this share of the source gets one shortening pass


@register_skill
class Summarizer(Skill):
    card = SkillCard(
        name="summarizer",
        summary="Condenses a given text into a shorter summary.",
        use_when="the user supplies a text (or refers to a text in the prompt) and wants it "
        "shortened, summarized, condensed or turned into key points / a TL;DR.",
        examples=("summarize this article: ...", "این متن را خلاصه کن: ...", "tl;dr of: ..."),
        keywords=(
            "summarize",
            "summary",
            "summarise",
            "tl;dr",
            "tldr",
            "key points",
            "condense",
            "shorten",
            "gist",
            "خلاصه",
            "چکیده",
            "نکات کلیدی",
            "مختصر",
            "کوتاه کن",
        ),
        titles={"en": "Summary", "fa": "خلاصه"},
    )

    def run(self, task: SkillTask) -> SkillOutput:
        text = task.input_text if task.input_text is not None else split_instruction(task.prompt)[1]
        if len(text.split()) < _MIN_WORDS:
            # "Summarize this" with nothing attached: ask for the text instead of letting the
            # model summarize the instruction itself (a routing slip seen in evaluation).
            return SkillOutput(text=t("clarify.need_text", task.language), notes=["no text given"])

        system = load_prompt("summarizer")
        message = task_message(task)
        if not self.budget.fits(system, message, task.max_output_tokens):
            return self._map_reduce(system, task)

        reply = self.llm.complete(system, message, max_tokens=task.max_output_tokens)
        source_words, summary_words = len(text.split()), len(reply.text.split())
        if source_words < _CHECK_FROM_WORDS or summary_words <= _MAX_RATIO * source_words:
            return SkillOutput(text=reply.text, usage=reply.usage)

        # The model sometimes restates the text instead of condensing it; ask once, with numbers.
        target = int(source_words * 0.4)
        repair = (
            f"{message}\n\nYour previous summary:\n<summary>\n{reply.text}\n</summary>\n"
            f"It has {summary_words} words but the source has only {source_words}. Rewrite it "
            f"in at most {target} words, keeping the main point and the key facts and any "
            "format the user asked for. Return only the summary."
        )
        shorter = self.llm.complete(system, repair, max_tokens=task.max_output_tokens)
        return SkillOutput(
            text=shorter.text,
            usage=reply.usage + shorter.usage,
            notes=[f"shortened after check: {summary_words} -> {len(shorter.text.split())} words"],
        )

    def _map_reduce(self, system: str, task: SkillTask) -> SkillOutput:
        """Summarize each chunk, then summarize the partial summaries.

        Every call stays within the window no matter how long the input is; the reduce step is
        repeated (up to a few rounds) while the partial summaries are themselves too long.
        """
        if task.input_text is not None:
            request, text = task.prompt, task.input_text
        else:
            request, text = split_instruction(task.prompt)
        chunk_budget = self.settings.chunk_tokens
        usage = Usage()
        total_chunks = 0

        for _ in range(_MAX_REDUCE_ROUNDS):
            chunks = chunk_text(text, chunk_budget)
            total_chunks += len(chunks)
            partials = []
            for i, chunk in enumerate(chunks, 1):
                part = task.model_copy(
                    update={
                        "prompt": request or "Summarize the text.",
                        "input_text": chunk,
                        "instruction": f"This is part {i} of {len(chunks)} of a longer text. "
                        "Summarize only this part and keep every key fact, name and number.",
                    }
                )
                reply = self.llm.complete(
                    system, task_message(part), max_tokens=task.max_output_tokens
                )
                usage += reply.usage
                partials.append(reply.text)
            text = "\n\n".join(partials)
            if estimate_tokens(text) <= chunk_budget:
                break

        final = task.model_copy(
            update={
                "prompt": request or task.prompt[:500],
                "input_text": text,
                "instruction": "The text consists of summaries of consecutive parts of one "
                "document. Merge them into a single summary that fulfils the original request. "
                + task.instruction,
            }
        )
        reply = self.llm.complete(system, task_message(final), max_tokens=task.max_output_tokens)
        return SkillOutput(
            text=reply.text,
            usage=usage + reply.usage,
            notes=[f"map-reduce over {total_chunks} chunks"],
        )
