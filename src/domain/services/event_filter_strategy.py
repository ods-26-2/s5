from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities.normalized_event import NormalizedEvent


class EventFilterStrategy(ABC):
    """Decide se um evento normalizado deve ser aceito no fluxo de domínio."""

    @abstractmethod
    def should_accept(self, event: NormalizedEvent) -> bool: ...


class DebounceHysteresisFilterStrategy(EventFilterStrategy):
    """Rejeita eventos repetidos da mesma origin dentro de um intervalo mínimo,
    suprimindo tanto rajadas (debounce) quanto a oscilação de ruído na borda
    de uma zona (histerese)."""

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._last_accepted_at: dict[str, datetime] = {}

    def should_accept(self, event: NormalizedEvent) -> bool:
        last_accepted_at = self._last_accepted_at.get(event.origin)
        if last_accepted_at is not None:
            elapsed_seconds = (event.timestamp - last_accepted_at).total_seconds()
            if elapsed_seconds < self._min_interval_seconds:
                return False

        self._last_accepted_at[event.origin] = event.timestamp
        return True
