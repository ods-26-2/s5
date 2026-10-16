import re
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.exceptions import InvalidEnvelopeError

MESSAGE_TYPES = frozenset({"event", "command", "query", "reply"})
SCHEMA_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Envelope:
    """Envelope comum de 13 campos de toda mensagem textual (Especificação 1.0, seção 3).

    Os seis primeiros campos são fixos em todo perfil; os demais dependem do perfil
    (EV-SINAL, EV-SERVIÇO, CMD, RPL) e por isso são opcionais aqui. Datetimes são UTC
    sem tzinfo, convenção de todo o S5.
    """

    message_type: str
    message_id: str
    schema: str
    schema_version: str
    producer: str
    published_at: datetime
    payload: dict = field(compare=False)
    captured_at: datetime | None = None
    source_id: str | None = None
    session_id: str | None = None
    sequence: int | None = None
    artifact_version: str | None = None
    correlation_id: str | None = None
    target: str | None = None

    def __post_init__(self) -> None:
        if self.message_type not in MESSAGE_TYPES:
            raise InvalidEnvelopeError(f"message_type inválido: {self.message_type!r}.")
        for name in ("message_id", "schema", "producer"):
            if not getattr(self, name).strip():
                raise InvalidEnvelopeError(f"{name} não pode ser vazio.")
        if not SCHEMA_VERSION_PATTERN.match(self.schema_version):
            raise InvalidEnvelopeError(
                f"schema_version deve seguir MAJOR.MINOR, recebido {self.schema_version!r}."
            )
        if self.sequence is not None and self.sequence < 0:
            raise InvalidEnvelopeError("sequence não pode ser negativo.")

    @property
    def schema_major(self) -> int:
        return int(SCHEMA_VERSION_PATTERN.match(self.schema_version).group(1))
