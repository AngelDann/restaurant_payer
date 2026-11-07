from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatAgentDeps:
    """Dependencies injected into every tool via `RunContext[ChatAgentDeps]`."""

    user_id: int | str
    tenant_id: int | str | None = None
    organization_id: int | str | None = None
    conversation_id: str | None = None

    def __post_init__(self) -> None:
        if self.tenant_id is None and self.organization_id is None:
            msg = "ChatAgentDeps requires at least one of tenant_id or organization_id"
            raise ValueError(msg)
