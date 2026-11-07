"""Celery entrypoints for AI chat (keep tasks thin; domain logic lives beside the agent)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.ai_chat.agent import ChatAgentDeps, stream_ai_turn
from config.celery import app

logger = logging.getLogger(__name__)


async def _silent_token(_: str) -> None:
    return None


async def _silent_tool(_: dict[str, Any]) -> None:
    return None


@app.task(name="ai_chat.run_turn_best_effort")
def run_ai_chat_turn_best_effort(
    user_text: str,
    user_id: int | str,
    tenant_id: int | str | None,
    organization_id: int | str | None,
    conversation_id: str | None = None,
    *,
    model_name: str | None = None,
    include_builtin_web_search: bool = False,
) -> dict[str, Any]:
    """Sync Celery wrapper: runs one streamed turn without forwarding tokens (batch / fire-and-forget).

    Returns ``{"text": ..., "usage": serialized_or_none}``. For WebSocket streaming, call
    ``stream_ai_turn`` from an async consumer instead.
    """
    deps = ChatAgentDeps(
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )

    async def _run() -> tuple[str, Any]:
        text, usage = await stream_ai_turn(
            user_text=user_text,
            attachments=(),
            message_history=[],
            deps=deps,
            emit_token=_silent_token,
            emit_tool=_silent_tool,
            model_name=model_name,
            include_builtin_web_search=include_builtin_web_search,
        )
        return text, usage

    text, usage = asyncio.run(_run())
    usage_payload: dict[str, Any] | None
    if usage is None:
        usage_payload = None
    else:
        usage_payload = {
            "requests": usage.requests,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
    logger.info("ai_chat.run_turn_best_effort completed for user=%s conv=%s", user_id, conversation_id)
    return {"text": text, "usage": usage_payload}
