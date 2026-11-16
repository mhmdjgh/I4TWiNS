from __future__ import annotations

from skill_agent.prompts import load_prompt
from skill_agent.skills.base import Skill, SkillCard, SkillOutput, SkillTask
from skill_agent.skills.registry import register_skill


@register_skill
class GeneralChat(Skill):
    """Conversation, general questions, and the fallback for anything no other skill covers."""

    card = SkillCard(
        name="general_chat",
        summary="Handles greetings, small talk and general questions.",
        use_when="the message is conversational or a general question that does not ask to "
        "summarize, translate or calculate. Also the fallback when nothing else fits.",
        examples=("hi, how are you?", "سلام، خوبی؟", "what can you do?"),
        keywords=(
            "hi",
            "hello",
            "thanks",
            "how are you",
            "who are you",
            "what can you do",
            "سلام",
            "خوبی",
            "ممنون",
            "مرسی",
            "چطوری",
            "کی هستی",
        ),
        titles={"en": "Reply", "fa": "پاسخ"},
    )

    def run(self, task: SkillTask) -> SkillOutput:
        reply = self.llm.complete(
            load_prompt("general_chat"), task.prompt, max_tokens=task.max_output_tokens
        )
        return SkillOutput(text=reply.text, usage=reply.usage)
