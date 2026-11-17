from __future__ import annotations

from skill_agent.context.chunking import chunk_text
from skill_agent.llm import Usage
from skill_agent.prompts import load_prompt
from skill_agent.skills.base import (
    Skill,
    SkillCard,
    SkillOutput,
    SkillTask,
    request_and_text,
    task_message,
)
from skill_agent.skills.checks import target_code, translation_issues
from skill_agent.skills.registry import register_skill

_REPAIR_TEMPERATURES = (0.0, 0.7)


def _repair_request(message: str, translation: str, issues: list[str]) -> str:
    problems = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{message}\n\n"
        f"Your previous translation:\n<translation>\n{translation}\n</translation>\n"
        f"It has these problems:\n{problems}\nReturn the corrected translation only."
    )


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
        request, source = request_and_text(task)
        delimited = task.input_text is not None or bool(request)
        target = target_code(task.target_language, source)

        def check(text: str) -> list[str]:
            return translation_issues(source, text, check_numbers=delimited, target=target)

        text, issues, usage = reply.text, check(reply.text), reply.usage
        notes: list[str] = []
        # Targeted corrections: the model is told exactly which facts it got wrong. The first try
        # is deterministic; when it repeats the mistake, a warmer second try usually doesn't.
        for temperature in _REPAIR_TEMPERATURES:
            if not issues:
                break
            notes.append(f"corrected after check: {'; '.join(issues)}")
            fixed = self.llm.complete(
                system,
                _repair_request(message, text, issues),
                max_tokens=task.max_output_tokens,
                temperature=temperature,
            )
            usage += fixed.usage
            remaining = check(fixed.text)
            if len(remaining) <= len(issues):
                text, issues = fixed.text, remaining
        if issues:
            notes.append(f"still flagged: {'; '.join(issues)}")
        return SkillOutput(text=text, usage=usage, notes=notes)

    def _chunked(self, system: str, task: SkillTask) -> SkillOutput:
        """Translate a long text chunk by chunk.

        Unlike summarization the output is as long as the input, so each chunk gets the full
        output allowance and the pieces are joined in order.
        """
        request, text = request_and_text(task)
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
