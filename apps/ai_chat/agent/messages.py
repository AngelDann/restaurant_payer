from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserContent,
    UserPromptPart,
)

logger = logging.getLogger(__name__)


def build_user_multimodal_prompt(
    text: str,
    attachments: Sequence[tuple[bytes, str]],
) -> list[UserContent]:
    """Build user prompt parts: leading text plus `BinaryContent` per attachment."""
    parts: list[UserContent] = []
    t = (text or "").strip()
    if t:
        parts.append(t)
    for raw, media_type in attachments:
        mt = (media_type or "application/octet-stream").strip()
        parts.append(BinaryContent(data=raw, media_type=mt))
    if not parts:
        parts.append("")
    return parts


def conversation_to_model_messages(
    messages: Sequence[Any],
    *,
    exclude_incomplete_assistant: bool = True,
) -> list[ModelMessage]:
    """Map stored conversation rows (duck-typed) to ModelMessage list.

    Each item should expose: role (user, assistant, system), content (str).
    Optional: is_draft; is_incomplete or incomplete (skip incomplete assistant rows when flag is True).
    Optional metadata on rows is reserved for future internal system lines (see commented hook in source).
    """
    out: list[ModelMessage] = []
    for m in messages:
        role = (getattr(m, "role", None) or "").strip().lower()
        if role in ("", "tool", "function"):
            continue
        if getattr(m, "is_draft", False):
            continue
        if exclude_incomplete_assistant and role == "assistant":
            if getattr(m, "is_incomplete", False) or getattr(m, "incomplete", False):
                continue
        content = getattr(m, "content", None)
        text = content if isinstance(content, str) else str(content or "")

        if role == "user":
            out.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        elif role == "assistant":
            out.append(ModelResponse(parts=[TextPart(content=text)]))
        elif role == "system":
            # md = getattr(m, "metadata", None)
            # if isinstance(md, dict) and md.get("internal"):
            #     out.append(ModelRequest(parts=[SystemPromptPart(content=text)], metadata=md))
            #     continue
            out.append(ModelRequest(parts=[SystemPromptPart(content=text)]))
        else:
            logger.debug("conversation_to_model_messages: skipped unknown role %r", role)
    return out
