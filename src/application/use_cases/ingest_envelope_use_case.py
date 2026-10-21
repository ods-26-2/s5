from collections.abc import Callable
from dataclasses import dataclass

from src.application.parsers.envelope_parser import (
    EV_SERVICO_FIELDS,
    EV_SINAL_FIELDS,
    EV_SINAL_SESSION_FIELDS,
    parse_envelope,
    parse_utc_timestamp,
)
from src.domain.entities.position_sample import PositionSample, TrackPosition
from src.domain.entities.qualified_event import QualifiedEvent
from src.domain.entities.replay_state import ReplayState
from src.domain.entities.session_start import SessionStart
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
POSITION_SCHEMA = "ods.s1.position"
QUALIFIED_EVENT_SCHEMA = "ods.s2.event"
SESSION_STARTED_SCHEMA = "ods.session.started"
REPLAY_STATE_SCHEMA = "ods.p6.replay.state"
SUPPORTED_MAJOR_VERSION = 1

DomainMessage = (
    ZoneTransition | ZoneOccupancySample | PositionSample | QualifiedEvent | SessionStart | ReplayState
)


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
            POSITION_SCHEMA: self._parse_position,
            QUALIFIED_EVENT_SCHEMA: self._parse_qualified_event,
            SESSION_STARTED_SCHEMA: self._parse_session_started,
            REPLAY_STATE_SCHEMA: self._parse_replay_state,
        }
        self._profile_fields = {
            ZONE_TRANSITION_SCHEMA: EV_SINAL_FIELDS,
            ZONE_OCCUPANCY_SCHEMA: EV_SINAL_FIELDS,
            POSITION_SCHEMA: EV_SINAL_FIELDS,
            QUALIFIED_EVENT_SCHEMA: EV_SERVICO_FIELDS,
            SESSION_STARTED_SCHEMA: EV_SINAL_SESSION_FIELDS,
            REPLAY_STATE_SCHEMA: EV_SINAL_SESSION_FIELDS,
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
    def _parse_position(envelope: Envelope) -> PositionSample:
        payload = envelope.payload
        return PositionSample(
            source_id=envelope.source_id,
            session_id=envelope.session_id,
            observed_at=envelope.captured_at,
            frame_index=payload["frame_index"],
            positions=tuple(
                TrackPosition(
                    track_id=item["track_id"],
                    object_class=item["class"],
                    point_px=_pair(item["point_px"], "point_px"),
                    zone_ids=tuple(item["zone_ids"]),
                    position_m=_pair(item["position_m"], "position_m") if "position_m" in item else None,
                    space_id=item.get("space_id"),
                )
                for item in payload["positions"]
            ),
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

    @staticmethod
    def _parse_session_started(envelope: Envelope) -> SessionStart:
        payload = envelope.payload
        sources = payload["sources"]
        if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
            raise TypeError("sources deve ser uma lista de strings.")
        return SessionStart(
            session_id=envelope.session_id,
            mode=payload["mode"],
            started_at=parse_utc_timestamp(payload["started_at"], "started_at"),
            sources=tuple(sources),
            recording_id=payload.get("recording_id"),
            previous_session_id=payload.get("previous_session_id"),
            reason=payload.get("reason"),
        )

    @staticmethod
    def _parse_replay_state(envelope: Envelope) -> ReplayState:
        payload = envelope.payload
        return ReplayState(
            session_id=envelope.session_id,
            captured_at=envelope.captured_at,
            recording_id=payload["recording_id"],
            state=payload["state"],
            position_ms=payload["position_ms"],
            duration_ms=payload["duration_ms"],
            speed_factor=payload["speed_factor"],
            loop=payload["loop"],
        )


def _pair(value: object, field_name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2 or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in value
    ):
        raise TypeError(f"{field_name} deve ser [x, y] numérico.")
    return (float(value[0]), float(value[1]))
