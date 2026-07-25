"""Deterministic route selection from an acceptance-time snapshot."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteConfig:
    mode: str
    version: int
    webhook: str | None = None

    def __post_init__(self):
        if self.mode not in {"internal_agent", "external_webhook"}:
            raise ValueError("unsupported automation mode")
        if self.mode == "external_webhook" and not self.webhook:
            raise ValueError("external mode requires a webhook")


def route_work(chat_id: str, owner_id: str | None, snapshot: RouteConfig) -> str:
    """Return the only route allowed by the immutable snapshot."""
    if owner_id:
        return "suppressed"
    return snapshot.mode
