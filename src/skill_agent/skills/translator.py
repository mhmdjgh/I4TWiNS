from __future__ import annotations

from skill_agent.prompts import load_prompt
from skill_agent.skills.base import Skill, SkillCard, SkillOutput, SkillTask, task_message
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
        reply = self.llm.complete(
            load_prompt("translator"), task_message(task), max_tokens=task.max_output_tokens
        )
        return SkillOutput(text=reply.text, usage=reply.usage)
