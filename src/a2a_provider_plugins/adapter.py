"""Small provider boundary kept separate from the A2A protocol model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderReply:
    """A provider response that can be represented as an A2A artifact."""

    text: str
    provider_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(ABC):
    """Translate a provider's native conversation API to one A2A task turn."""

    @abstractmethod
    async def send(
        self,
        text: str,
        *,
        context_id: str,
        task_id: str,
    ) -> ProviderReply:
        """Run one provider turn and return its final response."""

    @abstractmethod
    async def cancel(self, *, task_id: str) -> None:
        """Request cancellation for a running provider turn."""
