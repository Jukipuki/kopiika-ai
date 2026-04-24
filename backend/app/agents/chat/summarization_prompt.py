"""Pinned summarization prompt for chat memory compression (Story 10.4a AC #9).

Kept in a separate module from ``session_handler.py`` so the prompt is
reviewable as data (grep, diff, PR-comment) without scrolling through
handler control-flow. Called by ``session_handler._summarize`` only.
"""

from __future__ import annotations

from typing import Iterable

SUMMARIZATION_TEMPLATE = """\
You are summarizing the earlier portion of a financial chat conversation
for memory compression. Preserve: factual claims the user made, questions
they asked, assistant conclusions, any numeric figures cited. Omit:
pleasantries, repetition, meta-conversation. Output a single paragraph
<= 200 words in the same language the user was writing in (UA or EN).
Do not editorialize; do not add caveats.

Earlier conversation:
{older_messages_rendered}
"""


def render(older_messages: Iterable) -> str:
    """Render ``older_messages`` into the prompt template.

    Each message is formatted as ``"<ROLE>: <content>"`` on its own line;
    the ordered block is interpolated into the template's placeholder.
    """
    lines = []
    for m in older_messages:
        lines.append(f"{m.role.upper()}: {m.content}")
    return SUMMARIZATION_TEMPLATE.format(older_messages_rendered="\n".join(lines))
