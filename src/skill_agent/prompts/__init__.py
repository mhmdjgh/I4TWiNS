"""Prompt templates live next to this module as Markdown files so they can be reviewed and
versioned independently of the code. Placeholders use `{{name}}` to stay clear of JSON braces."""

from __future__ import annotations

import re
from functools import cache
from importlib import resources

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@cache
def load_prompt(name: str) -> str:
    return resources.files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8").strip()


def render(template: str, **values: object) -> str:
    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"missing value for prompt placeholder {key!r}")
        return str(values[key])

    return _PLACEHOLDER.sub(substitute, template)
