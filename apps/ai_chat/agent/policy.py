from __future__ import annotations

from django.conf import settings


class QuotaPolicyNotConfigured(RuntimeError):
    """Raised when `AI_CHAT_ENFORCE_QUOTA` is enabled but no quota hook is wired."""


def assert_can_run(
    user_id: int | str,
    tenant_id: int | str | None,
    organization_id: int | str | None,
    model: str,
) -> None:
    """Hook for quotas / billing. Default: no-op. Enable `AI_CHAT_ENFORCE_QUOTA` to enforce a policy later."""
    if not getattr(settings, "AI_CHAT_ENFORCE_QUOTA", False):
        return
    raise QuotaPolicyNotConfigured(
        "AI_CHAT_ENFORCE_QUOTA is True but quota checks are not implemented. "
        "Wire billing or caps into assert_can_run in apps.ai_chat.agent.policy."
    )
