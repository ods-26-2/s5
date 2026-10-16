import logging
from collections.abc import Callable

from src.application.use_cases.handle_bus_message_use_case import HandleBusMessageUseCase
from src.domain.exceptions import ODSBaseException
from src.infrastructure.b3_bus.b3_event_consumer import B3EventConsumer

logger = logging.getLogger(__name__)

ErrorCallback = Callable[[dict, ODSBaseException], None]


def _log_rejected(message: dict, error: ODSBaseException) -> None:
    logger.warning(
        "Mensagem rejeitada (schema=%s, message_id=%s): %s",
        message.get("schema"),
        message.get("message_id"),
        error,
    )


def subscribe_s5(
    consumer: B3EventConsumer,
    handler: HandleBusMessageUseCase,
    on_error: ErrorCallback = _log_rejected,
) -> None:
    """Assina um tópico por schema consumido pelo S5. Uma mensagem fora do contrato é
    registrada e descartada, sem derrubar a assinatura nem as mensagens seguintes."""

    def handle(message: dict) -> None:
        try:
            handler.execute(message)
        except ODSBaseException as error:
            on_error(message, error)

    for schema in handler.supported_schemas:
        consumer.subscribe(schema, handle)
