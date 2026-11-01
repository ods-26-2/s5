from dataclasses import dataclass, field
from datetime import datetime

from src.domain.exceptions import InvalidSessionError

LIVE = "LIVE"
REPLAY = "REPLAY"
SESSION_REASONS = frozenset({"START", "SEEK", "LOOP", "RESTART", "RECONNECT"})


@dataclass(frozen=True)
class SessionStart:
    """Início de uma sessão de captura ou replay (ods.session.started). Toda mensagem
    seguinte com este session_id tem o tempo de captura contado a partir de started_at;
    o estado mantido para a sessão anterior deixa de valer."""

    session_id: str
    mode: str
    started_at: datetime
    sources: tuple[str, ...] = field(default=())
    recording_id: str | None = None
    previous_session_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise InvalidSessionError("session_id não pode ser vazio.")
        if self.mode not in (LIVE, REPLAY):
            raise InvalidSessionError(f"mode inválido: {self.mode!r}.")
        if self.reason is not None and self.reason not in SESSION_REASONS:
            raise InvalidSessionError(f"reason inválida: {self.reason!r}.")
