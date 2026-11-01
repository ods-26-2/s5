from collections.abc import Callable

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.parsers.envelope_parser import parse_envelope
from src.application.ports.event_publisher import IEventPublisher
from src.domain.exceptions import MalformedEventEnvelopeError, QueryRejectedError, UnsupportedSchemaError

PRODUCER_ID = "S5"
QueryHandler = Callable[[dict], dict]


def reply_schema_for(query_schema: str) -> str:
    """ods.s5.metrics.query → ods.s5.metrics.reply (seção 2, regra 1)."""
    return query_schema.removesuffix(".query") + ".reply"


class AnswerQueryUseCase:
    """Recebe uma consulta dirigida ao S5 e publica a reply no tópico do schema de reply.

    O envelope segue o perfil CMD (target obrigatório). Consulta para outro target é
    ignorada. Consulta recusada vira reply com status ERROR e error {code, message};
    consulta sem envelope legível não tem a quem responder e sobe como erro. Consultas
    não alteram estado, então uma repetida é respondida de novo, em vez de descartada.
    """

    def __init__(
        self,
        handlers: dict[str, QueryHandler],
        envelope_factory: OutgoingEnvelopeFactory,
        publisher: IEventPublisher,
    ) -> None:
        self._handlers = handlers
        self._envelope_factory = envelope_factory
        self._publisher = publisher

    @property
    def supported_schemas(self) -> tuple[str, ...]:
        return tuple(self._handlers)

    def execute(self, raw_message: dict) -> dict | None:
        schema = raw_message.get("schema")
        handler = self._handlers.get(schema)
        if handler is None:
            raise UnsupportedSchemaError(f"Consulta não atendida pelo S5: {schema!r}.")
        envelope = parse_envelope(raw_message, required_fields=("target",))
        if envelope.message_type != "query":
            raise MalformedEventEnvelopeError(f"{schema} exige message_type query.")
        if envelope.target != PRODUCER_ID:
            return None

        try:
            payload = {"status": "OK", **handler(envelope.payload)}
        except QueryRejectedError as error:
            payload = {"status": "ERROR", "error": {"code": error.code, "message": error.message}}

        reply_schema = reply_schema_for(schema)
        reply = self._envelope_factory.reply(reply_schema, envelope.message_id, payload)
        self._publisher.publish(reply_schema, reply)
        return reply
