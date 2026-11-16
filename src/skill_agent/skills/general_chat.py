from __future__ import annotations

from skill_agent.context.tokens import excerpt
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
        system = load_prompt("general_chat")
        room = self.budget.input_room(system, task.max_output_tokens)
        message = excerpt(task.prompt, room)
        reply = self.llm.complete(system, message, max_tokens=task.max_output_tokens)
        notes = ["message excerpted to fit the context"] if message is not task.prompt else []
        return SkillOutput(text=reply.text, usage=reply.usage, notes=notes)
