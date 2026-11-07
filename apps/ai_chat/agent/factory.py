from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.builtin_tools import WebSearchTool

from apps.ai_chat.agent.deps import ChatAgentDeps
from apps.ai_chat.agent.runtime import (
    agent_model_string_for_transport,
    configure_openai_runtime_from_django,
    load_system_instructions,
    resolve_agent_model_name,
)

logger = logging.getLogger(__name__)


def _tool_ok(message: str = "ok", suggestions: list[str] | None = None) -> dict[str, Any]:
    return {"ok": True, "message": message, "suggestions": list(suggestions or [])}


def _tool_error(message: str, suggestions: list[str] | None = None) -> dict[str, Any]:
    return {"ok": False, "message": message, "suggestions": list(suggestions or ["Retry the request", "Contact support"])}


def build_main_agent(
    model_name: str | None = None,
    *,
    include_builtin_web_search: bool = False,
    defer_model_check: bool = True,
) -> Agent[ChatAgentDeps, str]:
    """Construct the shared `Agent` (string output, product-agnostic tools).

    Model id sent to Pydantic AI follows `AI_OPENAI_TRANSPORT`:
    - ``responses`` → ``openai-responses:{OPENAI_CHAT_MODEL|...}`` (needed for many hosted builtins, e.g. web search)
    - otherwise → ``openai:{model}`` (chat completions transport)

    Builtin tools that require the Responses API must use the ``responses`` transport or the run may fail at runtime.
    """
    configure_openai_runtime_from_django()
    bare = resolve_agent_model_name(model_name)
    full_model = agent_model_string_for_transport(bare)
    transport = (getattr(settings, "AI_OPENAI_TRANSPORT", None) or "chat").strip().lower()
    if include_builtin_web_search and transport != "responses":
        raise ValueError(
            "include_builtin_web_search requires AI_OPENAI_TRANSPORT=responses "
            "so the agent uses openai-responses:...; web search and similar builtins are not supported on the chat transport."
        )

    instructions = load_system_instructions()
    builtins: list[WebSearchTool] = []
    if include_builtin_web_search:
        builtins.append(WebSearchTool())

    agent: Agent[ChatAgentDeps, str] = Agent(
        full_model,
        deps_type=ChatAgentDeps,
        output_type=str,
        instructions=instructions,
        builtin_tools=tuple(builtins),
        defer_model_check=defer_model_check,
    )

    @agent.tool
    async def get_tenant_stub(ctx: RunContext[ChatAgentDeps]) -> dict[str, Any]:
        try:
            return _tool_ok(
                f"context user={ctx.deps.user_id!r} tenant={ctx.deps.tenant_id!r} org={ctx.deps.organization_id!r}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_tenant_stub failed")
            return _tool_error(str(exc), ["Retry", "Verify session context"])

    @agent.tool
    async def echo_ping(ctx: RunContext[ChatAgentDeps], message: str = "") -> dict[str, Any]:
        try:
            msg = (message or "").strip() or "pong"
            return _tool_ok(msg)
        except Exception as exc:  # noqa: BLE001
            logger.exception("echo_ping failed")
            return _tool_error(str(exc), ["Send a shorter message"])

    return agent
