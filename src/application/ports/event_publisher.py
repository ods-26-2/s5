from abc import ABC, abstractmethod


class IEventPublisher(ABC):
    """Porta de publicação no barramento B3. O tópico é o nome do schema (um tópico por
    schema, frente B3); a mensagem já vem com o envelope completo."""

    @abstractmethod
    def publish(self, topic: str, message: dict) -> None: ...
