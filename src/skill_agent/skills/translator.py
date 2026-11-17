from __future__ import annotations

from skill_agent.context.chunking import chunk_text, split_instruction
from skill_agent.llm import Usage
from skill_agent.prompts import load_prompt
from skill_agent.skills.base import Skill, SkillCard, SkillOutput, SkillTask, task_message
from skill_agent.skills.checks import target_code, translation_issues
from skill_agent.skills.registry import register_skill


@register_skill
class Translator(Skill):
    card = SkillCard(
        name="translator",
        summary="Translates a given text between languages (Persian, English and others).",
        use_when="the user supplies a text and asks for it in another language, or asks how "
        "a phrase is said in another language.",
        examples=(
            "translate to English: ...",
            "این جمله را به انگلیسی ترجمه کن: ...",
            "what is 'thank you' in Persian?",
        ),
        keywords=(
            "translate",
            "translation",
            "in english",
            "in persian",
            "in farsi",
            "into",
            "ترجمه",
            "برگردان",
            "به انگلیسی",
            "به فارسی",
            "معادل",
        ),
        titles={"en": "Translation", "fa": "ترجمه"},
    )

    def run(self, task: SkillTask) -> SkillOutput:
        system = load_prompt("translator")
        message = task_message(task)
        if not self.budget.fits(system, message, task.max_output_tokens):
            return self._chunked(system, task)

        reply = self.llm.complete(system, message, max_tokens=task.max_output_tokens)
        if task.input_text is not None:
            source, delimited = task.input_text, True
        else:
            instruction, source = split_instruction(task.prompt)
            delimited = bool(instruction)
        issues = translation_issues(
            source,
            reply.text,
            check_numbers=delimited,
            target=target_code(task.target_language, source),
        )
        if not issues:
            return SkillOutput(text=reply.text, usage=reply.usage)

        # One targeted correction: the model is told exactly which facts it got wrong.
        problems = "\n".join(f"- {issue}" for issue in issues)
        repair = (
            f"{message}\n\n"
            f"Your previous translation:\n<translation>\n{reply.text}\n</translation>\n"
            f"It has these problems:\n{problems}\nReturn the corrected translation only."
        )
        fixed = self.llm.complete(
            system, repair, max_tokens=task.max_output_tokens, temperature=0.0
        )
        return SkillOutput(
            text=fixed.text,
            usage=reply.usage + fixed.usage,
            notes=[f"corrected after check: {'; '.join(issues)}"],
        )

    def _chunked(self, system: str, task: SkillTask) -> SkillOutput:
        """Translate a long text chunk by chunk.

        Unlike summarization the output is as long as the input, so each chunk gets the full
        output allowance and the pieces are joined in order.
        """
        if task.input_text is not None:
            request, text = task.prompt, task.input_text
        else:
            request, text = split_instruction(task.prompt)
        chunks = chunk_text(text, self.settings.chunk_tokens)
        usage = Usage()
        pieces = []
        for i, chunk in enumerate(chunks, 1):
            part = task.model_copy(
                update={
                    "prompt": request or "Translate the text.",
                    "input_text": chunk,
                    "instruction": f"{task.instruction} (part {i} of {len(chunks)}; translate "
                    "this part completely and output only its translation)".strip(),
                }
            )
            # A translation is about as long as its source (longer for Persian): size by chunk.
            reply = self.llm.complete(
                system, task_message(part), max_tokens=self.settings.chunk_tokens * 2
            )
            usage += reply.usage
            pieces.append(reply.text)
        return SkillOutput(
            text="\n\n".join(pieces),
            usage=usage,
            notes=[f"translated in {len(chunks)} chunks"],
        )
