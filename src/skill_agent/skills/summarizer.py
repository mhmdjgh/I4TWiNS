from __future__ import annotations

from skill_agent.prompts import load_prompt
from skill_agent.skills.base import Skill, SkillCard, SkillOutput, SkillTask, task_message
from skill_agent.skills.registry import register_skill


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
        reply = self.llm.complete(
            load_prompt("summarizer"), task_message(task), max_tokens=task.max_output_tokens
        )
        return SkillOutput(text=reply.text, usage=reply.usage)
