from datetime import datetime, timezone

from src.domain.exceptions import DomainError, MalformedEventEnvelopeError
from src.domain.value_objects.envelope import Envelope

FIXED_FIELDS = ("message_type", "message_id", "schema", "schema_version", "producer", "published_at")
EV_SINAL_FIELDS = ("captured_at", "source_id", "session_id", "sequence", "artifact_version")
EV_SERVICO_FIELDS = ("captured_at", "session_id", "sequence")
# ods.session.started e ods.p6.replay.state usam EV-SINAL sem artifact_version. source_id
# não é exigido: P6 reproduz várias fontes ao mesmo tempo, listadas no payload (sources).
EV_SINAL_SESSION_FIELDS = ("captured_at", "session_id", "sequence")


def parse_utc_timestamp(value: object, field_name: str) -> datetime:
    """Converte um marco ISO 8601 com fuso (ex.: 2026-09-23T14:29:59.870Z) em datetime UTC
    sem tzinfo. Marco sem fuso é rejeitado: a convenção da seção 2 exige UTC explícito."""
    if not isinstance(value, str):
        raise MalformedEventEnvelopeError(f"{field_name} deve ser string ISO 8601.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise MalformedEventEnvelopeError(f"{field_name} não é ISO 8601: {value!r}.") from error
    if parsed.tzinfo is None:
        raise MalformedEventEnvelopeError(f"{field_name} precisa de fuso (UTC, sufixo Z): {value!r}.")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def parse_envelope(raw: dict, required_fields: tuple[str, ...] = ()) -> Envelope:
    """Lê o envelope comum de uma mensagem do barramento. `required_fields` são os campos
    de contexto exigidos pelo perfil do schema (ex.: EV_SINAL_FIELDS)."""
    missing = [name for name in (*FIXED_FIELDS, *required_fields, "payload") if raw.get(name) is None]
    if missing:
        raise MalformedEventEnvelopeError(f"Campos obrigatórios ausentes no envelope: {missing}.")
    if not isinstance(raw["payload"], dict):
        raise MalformedEventEnvelopeError("payload deve ser um objeto.")

    sequence = raw.get("sequence")
    if sequence is not None and (not isinstance(sequence, int) or isinstance(sequence, bool)):
        raise MalformedEventEnvelopeError("sequence deve ser inteiro.")

    captured_at = raw.get("captured_at")
    try:
        return Envelope(
            message_type=raw["message_type"],
            message_id=raw["message_id"],
            schema=raw["schema"],
            schema_version=raw["schema_version"],
            producer=raw["producer"],
            published_at=parse_utc_timestamp(raw["published_at"], "published_at"),
            payload=raw["payload"],
            captured_at=parse_utc_timestamp(captured_at, "captured_at") if captured_at else None,
            source_id=raw.get("source_id"),
            session_id=raw.get("session_id"),
            sequence=sequence,
            artifact_version=raw.get("artifact_version"),
            correlation_id=raw.get("correlation_id"),
            target=raw.get("target"),
        )
    except (DomainError, AttributeError, TypeError) as error:
        raise MalformedEventEnvelopeError(f"Envelope inválido: {error}") from error
