"""Reusable Pydantic AI + OpenAI chat agent layer (domain-agnostic).

Environment (Django settings / `.env` via `python-decouple`):

- `OPENAI_API_KEY` — required for real runs (also synced into `os.environ` if missing).
- `OPENAI_BASE_URL` — optional compatible endpoint.
- `OPENAI_CHAT_MODEL` — preferred chat model id (falls back to `OPENAI_MODEL`, then `gpt-4o-mini`).
- `AI_OPENAI_TRANSPORT` — `responses` → model string `openai-responses:{model}`; any other value → `openai:{model}`.
  Hosted builtins such as web search often require the Responses transport when the provider mandates it.
- `AI_CHAT_SYSTEM_INSTRUCTIONS` — optional; when set, replaces file + fallback instructions entirely.
- `AI_CHAT_SYSTEM_PROMPT_PATH` — optional path to a Markdown system prompt (default: `prompts/main_system.md` under `BASE_DIR`).
- `AI_CHAT_ENFORCE_QUOTA` — when true, `assert_can_run` raises until you wire quotas.

Flow: load system instructions → build multimodal user parts → map stored rows to `ModelMessage` history →
`stream_ai_turn` runs `Agent.run_stream_events` with deps and callbacks.

Integration: Channels consumers or Celery tasks should call `stream_ai_turn` / `build_main_agent`; register
product tools by extending the agent or wrapping `build_main_agent`.
"""

from apps.ai_chat.agent.deps import ChatAgentDeps
from apps.ai_chat.agent.factory import build_main_agent
from apps.ai_chat.agent.messages import build_user_multimodal_prompt, conversation_to_model_messages
from apps.ai_chat.agent.policy import QuotaPolicyNotConfigured, assert_can_run
from apps.ai_chat.agent.runtime import (
    agent_model_string_for_transport,
    configure_openai_runtime_from_django,
    load_system_instructions,
    resolve_agent_model_name,
)
from apps.ai_chat.agent.streaming import stream_ai_turn

__all__ = [
    "ChatAgentDeps",
    "QuotaPolicyNotConfigured",
    "agent_model_string_for_transport",
    "assert_can_run",
    "build_main_agent",
    "build_user_multimodal_prompt",
    "configure_openai_runtime_from_django",
    "conversation_to_model_messages",
    "load_system_instructions",
    "resolve_agent_model_name",
    "stream_ai_turn",
]
