from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import InvalidSessionError

REPLAY_STATES = frozenset({"PLAYING", "PAUSED", "STOPPED"})


@dataclass(frozen=True)
class ReplayState:
    """Estado do replay publicado por P6 a cada mudança e a cada 1 s em reprodução
    (ods.p6.replay.state). Para o S5, o que importa é captured_at: é o relógio de
    captura da gravação, que avança mesmo quando nenhuma zona muda."""

    session_id: str
    captured_at: datetime
    recording_id: str
    state: str
    position_ms: int
    duration_ms: int
    speed_factor: float
    loop: bool

    def __post_init__(self) -> None:
        if not self.session_id.strip() or not self.recording_id.strip():
            raise InvalidSessionError("session_id e recording_id não podem ser vazios.")
        if self.state not in REPLAY_STATES:
            raise InvalidSessionError(f"state inválido: {self.state!r}.")
        if self.position_ms < 0 or self.duration_ms < 0:
            raise InvalidSessionError("position_ms e duration_ms não podem ser negativos.")
        if self.speed_factor <= 0:
            raise InvalidSessionError("speed_factor deve ser maior que zero.")
