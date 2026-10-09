from abc import ABC, abstractmethod
from collections.abc import Callable

EventHandler = Callable[[dict], None]


class B3EventConsumer(ABC):
    """Contrato de consumo do Barramento B3 (Pub/Sub). Espelha a interface já usada no
    S4 em C++ (mod2/s4-media-evidence/.../b3_event_consumer.hpp) para manter os dois
    serviços consistentes."""

    @abstractmethod
    def subscribe(self, topic: str, handler: EventHandler) -> None: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


class InMemoryB3EventConsumer(B3EventConsumer):
    """Implementação em memória, sem acoplar a um broker real. Útil para desenvolvimento,
    testes e como ponto de substituição por um client Pub/Sub de verdade."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def publish(self, topic: str, envelope: dict) -> None:
        if not self._running:
            return
        for handler in self._handlers.get(topic, []):
            handler(envelope)
