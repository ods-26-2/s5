from collections.abc import Callable
from dataclasses import dataclass

from src.application.parsers.envelope_parser import (
    EV_SERVICO_FIELDS,
    EV_SINAL_FIELDS,
    parse_envelope,
    parse_utc_timestamp,
)
from src.domain.entities.qualified_event import QualifiedEvent
from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ZoneTransition
from src.domain.exceptions import (
    DomainError,
    MalformedEventEnvelopeError,
    UnsupportedSchemaError,
    UnsupportedSchemaVersionError,
)
from src.domain.services.message_deduplicator import MessageDeduplicator
from src.domain.value_objects.envelope import Envelope

ZONE_TRANSITION_SCHEMA = "ods.s1.zone_transition"
ZONE_OCCUPANCY_SCHEMA = "ods.s1.zone_occupancy"
QUALIFIED_EVENT_SCHEMA = "ods.s2.event"
SUPPORTED_MAJOR_VERSION = 1

DomainMessage = ZoneTransition | ZoneOccupancySample | QualifiedEvent


@dataclass(frozen=True)
class IngestedMessage:
    """Mensagem aceita: o envelope (sessão, fonte, versão do artefato) e o objeto de domínio."""

    envelope: Envelope
    message: DomainMessage


class IngestEnvelopeUseCase:
    """Recebe uma mensagem bruta do barramento e a converte no objeto de domínio de S5.

    Ordem: lê o envelope, descarta reentregas pelo message_id (regra 7), recusa MAJOR
    desconhecido (regra 8) e interpreta o payload pelo schema. O message_id só é
    registrado depois que a mensagem é aceita, para que uma mensagem malformada
    reenviada corrigida não seja descartada como repetida.
    """

    def __init__(self, deduplicator: MessageDeduplicator) -> None:
        self._deduplicator = deduplicator
        self._payload_parsers: dict[str, Callable[[Envelope], DomainMessage]] = {
            ZONE_TRANSITION_SCHEMA: self._parse_zone_transition,
            ZONE_OCCUPANCY_SCHEMA: self._parse_zone_occupancy,
            QUALIFIED_EVENT_SCHEMA: self._parse_qualified_event,
        }
        self._profile_fields = {
            ZONE_TRANSITION_SCHEMA: EV_SINAL_FIELDS,
            ZONE_OCCUPANCY_SCHEMA: EV_SINAL_FIELDS,
            QUALIFIED_EVENT_SCHEMA: EV_SERVICO_FIELDS,
        }

    @property
    def supported_schemas(self) -> tuple[str, ...]:
        return tuple(self._payload_parsers)

    def execute(self, raw_message: dict) -> IngestedMessage | None:
        schema = raw_message.get("schema")
        payload_parser = self._payload_parsers.get(schema)
        if payload_parser is None:
            raise UnsupportedSchemaError(f"Schema não consumido pelo S5: {schema!r}.")

        envelope = parse_envelope(raw_message, required_fields=self._profile_fields[schema])
        if self._deduplicator.is_duplicate(envelope.message_id):
            return None
        if envelope.schema_major != SUPPORTED_MAJOR_VERSION:
            raise UnsupportedSchemaVersionError(
                f"{envelope.schema} {envelope.schema_version}: S5 conhece só o MAJOR "
                f"{SUPPORTED_MAJOR_VERSION}."
            )

        try:
            message = payload_parser(envelope)
        except KeyError as error:
            raise MalformedEventEnvelopeError(
                f"Campo obrigatório ausente no payload de {envelope.schema}: {error}"
            ) from error
        except (DomainError, AttributeError, TypeError) as error:
            raise MalformedEventEnvelopeError(f"Payload inválido em {envelope.schema}: {error}") from error

        self._deduplicator.register(envelope.message_id)
        return IngestedMessage(envelope=envelope, message=message)

    @staticmethod
    def _parse_zone_transition(envelope: Envelope) -> ZoneTransition:
        payload = envelope.payload
        return ZoneTransition(
            zone_id=payload["zone_id"],
            track_id=payload["track_id"],
            object_class=payload["class"],
            transition=payload["transition"],
            occurred_at=envelope.captured_at,
            entered_at=parse_utc_timestamp(payload["entered_at"], "entered_at"),
            source_id=envelope.source_id,
            session_id=envelope.session_id,
            dwell_s=payload.get("dwell_s"),
        )

    @staticmethod
    def _parse_zone_occupancy(envelope: Envelope) -> ZoneOccupancySample:
        payload = envelope.payload
        return ZoneOccupancySample(
            zone_id=payload["zone_id"],
            observed_at=envelope.captured_at,
            count=payload["count"],
            source_id=envelope.source_id,
            session_id=envelope.session_id,
            count_by_class=dict(payload["count_by_class"]),
            max_occupancy=payload.get("max_occupancy"),
        )

    @staticmethod
    def _parse_qualified_event(envelope: Envelope) -> QualifiedEvent:
        payload = envelope.payload
        return QualifiedEvent(
            event_id=payload["event_id"],
            event_type=payload["event_type"],
            status=payload["status"],
            phase=payload["phase"],
            started_at=parse_utc_timestamp(payload["started_at"], "started_at"),
            duration_ms=payload["duration_ms"],
            occurred_at=envelope.captured_at,
            session_id=envelope.session_id,
            zone_id=payload.get("zone_id"),
            object_class=payload.get("class"),
        )
