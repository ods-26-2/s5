import logging
from collections.abc import Callable
from typing import ContextManager, Protocol

from src.domain.exceptions import ODSBaseException
from src.infrastructure.b3_bus.b3_event_consumer import B3EventConsumer

logger = logging.getLogger(__name__)

ErrorCallback = Callable[[dict, ODSBaseException], None]


class MessageHandler(Protocol):
    """Caso de uso que recebe mensagens do barramento: HandleBusMessageUseCase (eventos)
    ou AnswerQueryUseCase (consultas)."""

    @property
    def supported_schemas(self) -> tuple[str, ...]: ...

    def execute(self, raw_message: dict) -> object: ...


def _log_rejected(message: dict, error: ODSBaseException) -> None:
    logger.warning(
        "Mensagem rejeitada (schema=%s, message_id=%s): %s",
        message.get("schema"),
        message.get("message_id"),
        error,
    )


class SerializedHandler:
    """Executa o handler sob um lock, para que a entrada de mensagens no buffer não se
    misture com o fechamento de janelas, que roda em outra thread."""

    def __init__(self, handler: MessageHandler, lock: ContextManager) -> None:
        self._handler = handler
        self._lock = lock

    @property
    def supported_schemas(self) -> tuple[str, ...]:
        return self._handler.supported_schemas

    def execute(self, raw_message: dict) -> object:
        with self._lock:
            return self._handler.execute(raw_message)


def subscribe_s5(
    consumer: B3EventConsumer,
    handler: MessageHandler,
    on_error: ErrorCallback = _log_rejected,
) -> None:
    """Assina um tópico por schema atendido pelo handler. Uma mensagem fora do contrato é
    registrada e descartada, sem derrubar a assinatura nem as mensagens seguintes."""

    def handle(message: dict) -> None:
        try:
            handler.execute(message)
        except ODSBaseException as error:
            on_error(message, error)

    for schema in handler.supported_schemas:
        consumer.subscribe(schema, handle)
