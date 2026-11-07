from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPartDelta,
    ToolCallPart,
)
from pydantic_ai.usage import RunUsage

from apps.ai_chat.agent.deps import ChatAgentDeps
from apps.ai_chat.agent.factory import build_main_agent
from apps.ai_chat.agent.messages import build_user_multimodal_prompt
from apps.ai_chat.agent.policy import assert_can_run
from apps.ai_chat.agent.runtime import configure_openai_runtime_from_django, resolve_agent_model_name

logger = logging.getLogger(__name__)


async def stream_ai_turn(
    *,
    user_text: str,
    attachments: Sequence[tuple[bytes, str]] | None = None,
    message_history: Sequence[ModelMessage] | None,
    deps: ChatAgentDeps,
    emit_token: Callable[[str], Awaitable[None]],
    emit_tool: Callable[[dict[str, Any]], Awaitable[None]],
    model_name: str | None = None,
    include_builtin_web_search: bool = False,
) -> tuple[str, RunUsage | None]:
    """Run one agent turn with streaming events.

    Returns ``(final_text, usage)`` for persistence / metering. Callbacks must be async.
    """
    configure_openai_runtime_from_django()
    bare = resolve_agent_model_name(model_name)
    assert_can_run(deps.user_id, deps.tenant_id, deps.organization_id, bare)

    user_parts = build_user_multimodal_prompt(user_text, attachments or ())
    agent = build_main_agent(
        model_name,
        include_builtin_web_search=include_builtin_web_search,
        defer_model_check=True,
    )

    final_text = ""
    usage: RunUsage | None = None

    async for event in agent.run_stream_events(
        user_parts,
        message_history=list(message_history or []),
        deps=deps,
    ):
        if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
            delta = event.delta.content_delta
            if delta:
                await emit_token(delta)
        elif isinstance(event, PartStartEvent):
            if isinstance(event.part, ToolCallPart):
                await emit_tool(
                    {
                        "phase": "start",
                        "kind": "function",
                        "name": event.part.tool_name,
                        "tool_call_id": event.part.tool_call_id,
                        "args": event.part.args,
                    }
                )
            elif isinstance(event.part, BuiltinToolCallPart):
                await emit_tool(
                    {
                        "phase": "start",
                        "kind": "builtin",
                        "name": event.part.tool_name,
                        "tool_call_id": event.part.tool_call_id,
                        "args": event.part.args,
                    }
                )
        elif isinstance(event, PartEndEvent):
            if isinstance(event.part, (ToolCallPart, BuiltinToolCallPart)):
                await emit_tool(
                    {
                        "phase": "end",
                        "kind": "builtin" if isinstance(event.part, BuiltinToolCallPart) else "function",
                        "name": event.part.tool_name,
                        "tool_call_id": event.part.tool_call_id,
                    }
                )
        elif isinstance(event, FunctionToolCallEvent):
            await emit_tool(
                {
                    "phase": "function_call",
                    "name": event.part.tool_name,
                    "tool_call_id": event.part.tool_call_id,
                    "args": event.part.args,
                    "args_valid": event.args_valid,
                }
            )
        elif isinstance(event, FunctionToolResultEvent):
            await emit_tool(
                {
                    "phase": "function_result",
                    "tool_call_id": event.tool_call_id,
                    "tool_name": event.result.tool_name,
                    "outcome": getattr(event.result, "outcome", None),
                }
            )
        elif isinstance(event, AgentRunResultEvent):
            final_text = str(event.result.output)
            usage = event.result.usage()

    return final_text, usage
