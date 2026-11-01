import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.domain.entities.position_sample import PositionSample, TrackPosition

METERS = "METERS"
PIXELS = "PIXELS"
# Resolução em que a presença é guardada. A consulta agrupa estas células finas no
# tamanho pedido, que por isso deve ser no mínimo a resolução base.
BASE_CELL_SIZE = {METERS: 0.1, PIXELS: 10.0}
# Intervalo máximo entre duas posições do mesmo rastro para que o tempo entre elas conte
# como presença. Acima disso houve perda de quadros ou de mensagens, e o intervalo é
# descartado em vez de atribuído a uma célula onde o objeto pode não ter ficado.
MAX_GAP_SECONDS = 1.0
BUCKET = timedelta(minutes=1)
EPOCH = datetime(1970, 1, 1)


@dataclass(frozen=True)
class PresenceKey:
    """Onde e quando a presença foi acumulada: espaço (space_id em METERS, source_id em
    PIXELS), classe, célula fina e minuto UTC, dentro de uma sessão."""

    session_id: str
    space_kind: str
    space_key: str
    object_class: str
    cell_x: int
    cell_y: int
    bucket_start: datetime


@dataclass(frozen=True)
class _LastSeen:
    observed_at: datetime
    position: TrackPosition


class PresenceAccumulator:
    """Soma, por célula fina e minuto, os segundos em que cada rastro esteve em cada lugar.

    O intervalo entre duas posições consecutivas do mesmo rastro é atribuído à célula da
    primeira: é onde o objeto estava durante aquele tempo. Câmeras diferentes acumulam
    separadamente, então uma pessoa vista por duas câmeras calibradas no mesmo espaço
    conta em dobro; a fusão entre câmeras é de S2 (ods.s2.entity).
    """

    def __init__(self) -> None:
        self._last_seen: dict[tuple[str, str, str], _LastSeen] = {}
        self._seconds: dict[PresenceKey, float] = {}

    def observe(self, sample: PositionSample) -> None:
        for position in sample.positions:
            track_key = (sample.session_id, sample.source_id, position.track_id)
            previous = self._last_seen.get(track_key)
            if previous is not None:
                elapsed = (sample.observed_at - previous.observed_at).total_seconds()
                if 0 < elapsed <= MAX_GAP_SECONDS:
                    self._add(sample, previous, elapsed)
            self._last_seen[track_key] = _LastSeen(sample.observed_at, position)

    def forget_tracks(self, session_id: str) -> None:
        """Esquece os rastros de uma sessão encerrada, mantendo o que já foi acumulado."""
        self._last_seen = {k: v for k, v in self._last_seen.items() if k[0] != session_id}

    def drain(self, session_id: str | None, until: datetime) -> dict[PresenceKey, float]:
        """Entrega e remove os minutos fechados: todos os de sessões que não são a
        corrente e, da corrente, os que terminam até `until`."""
        drained = {
            key: seconds
            for key, seconds in self._seconds.items()
            if key.session_id != session_id or key.bucket_start + BUCKET <= until
        }
        for key in drained:
            del self._seconds[key]
        return drained

    def _add(self, sample: PositionSample, previous: _LastSeen, elapsed: float) -> None:
        position = previous.position
        if position.position_m is not None:
            kind, space, point = METERS, position.space_id, position.position_m
        else:
            kind, space, point = PIXELS, sample.source_id, position.point_px
        size = BASE_CELL_SIZE[kind]
        key = PresenceKey(
            session_id=sample.session_id,
            space_kind=kind,
            space_key=space,
            object_class=position.object_class,
            cell_x=_cell_index(point[0], size),
            cell_y=_cell_index(point[1], size),
            bucket_start=EPOCH + ((previous.observed_at - EPOCH) // BUCKET) * BUCKET,
        )
        self._seconds[key] = self._seconds.get(key, 0.0) + elapsed


def _cell_index(coordinate: float, size: float) -> int:
    """Índice da célula que contém a coordenada. A tolerância evita que 7.10 / 0.1, que em
    ponto flutuante dá 70.999…, caia na célula 70 em vez da 71."""
    return math.floor(coordinate / size + 1e-9)
