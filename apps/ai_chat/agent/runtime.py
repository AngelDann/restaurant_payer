from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings


def configure_openai_runtime_from_django() -> None:
    """Sync OpenAI env vars from Django settings when the process environment is empty."""
    key = (getattr(settings, "OPENAI_API_KEY", None) or "").strip()
    if key and not (os.environ.get("OPENAI_API_KEY") or "").strip():
        os.environ["OPENAI_API_KEY"] = key
    base = (getattr(settings, "OPENAI_BASE_URL", None) or "").strip()
    if base and not (os.environ.get("OPENAI_BASE_URL") or "").strip():
        os.environ["OPENAI_BASE_URL"] = base


def resolve_agent_model_name(model_name: str | None) -> str:
    """Return the bare OpenAI model id (no openai: / openai-responses: prefix)."""
    if model_name and model_name.strip():
        return model_name.strip()
    chat = (getattr(settings, "OPENAI_CHAT_MODEL", None) or "").strip()
    if chat:
        return chat
    return (getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini").strip()


def agent_model_string_for_transport(bare_model: str) -> str:
    """Build Pydantic AI model id: `openai:{model}` or `openai-responses:{model}`."""
    transport = (getattr(settings, "AI_OPENAI_TRANSPORT", None) or "chat").strip().lower()
    if transport == "responses":
        return f"openai-responses:{bare_model}"
    return f"openai:{bare_model}"


def load_system_instructions() -> str:
    """Order: AI_CHAT_SYSTEM_INSTRUCTIONS → Markdown file → code fallback."""
    override = (getattr(settings, "AI_CHAT_SYSTEM_INSTRUCTIONS", None) or "").strip()
    if override:
        return override

    path_str = getattr(settings, "AI_CHAT_SYSTEM_PROMPT_PATH", None) or ""
    path = Path(path_str) if path_str else Path(settings.BASE_DIR) / "prompts" / "main_system.md"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()

    return _FALLBACK_SYSTEM_INSTRUCTIONS


_FALLBACK_SYSTEM_INSTRUCTIONS = """\
# Assistant

You are a neutral product assistant. Use **Markdown** when it helps clarity.

- Use **tools** to confirm internal or live data before stating it as fact.
- If a tool fails or is missing, say so briefly and suggest alternatives.

"""
