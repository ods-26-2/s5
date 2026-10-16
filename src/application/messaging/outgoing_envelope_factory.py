import uuid
from collections.abc import Callable
from datetime import datetime, timezone

PRODUCER = "S5"
SCHEMA_VERSION = "1.0"


def format_utc(instant: datetime) -> str:
    """Datetime UTC sem tzinfo → ISO 8601 com milissegundos e sufixo Z (seção 2, regra 2)."""
    return f"{instant.isoformat(timespec='milliseconds')}Z"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OutgoingEnvelopeFactory:
    """Monta mensagens de evento do S5 com o perfil EV-SERVIÇO (seção 3).

    sequence é um contador crescente por session_id, a partir de 0, para que o consumidor
    detecte perda. Relógio e gerador de ids são injetáveis para os testes.
    """

    def __init__(
        self,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory
        self._next_sequence: dict[str, int] = {}

    def service_event(
        self,
        schema: str,
        payload: dict,
        captured_at: datetime,
        session_id: str,
        source_id: str | None = None,
        artifact_version: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        sequence = self._next_sequence.get(session_id, 0)
        self._next_sequence[session_id] = sequence + 1

        message = {
            "message_type": "event",
            "message_id": self._id_factory(),
            "schema": schema,
            "schema_version": SCHEMA_VERSION,
            "producer": PRODUCER,
            "published_at": format_utc(self._clock()),
            "captured_at": format_utc(captured_at),
            "session_id": session_id,
            "sequence": sequence,
        }
        optional = {
            "source_id": source_id,
            "artifact_version": artifact_version,
            "correlation_id": correlation_id,
        }
        message.update({name: value for name, value in optional.items() if value is not None})
        message["payload"] = payload
        return message
