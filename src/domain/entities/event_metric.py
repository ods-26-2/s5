from dataclasses import dataclass

from src.domain.exceptions import InvalidEventMetricError
from src.domain.value_objects.time_window import TimeWindow


@dataclass(frozen=True)
class EventMetric:
    """Métrica de um tipo de evento qualificado em uma janela, nas dimensões zona e classe
    (ausentes quando o evento não as tem). count inclui os eventos em dúvida;
    uncertain_count é o subconjunto deles."""

    event_type: str
    window: TimeWindow
    count: int
    uncertain_count: int
    zone_id: str | None = None
    object_class: str | None = None
    duration_avg_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise InvalidEventMetricError("event_type não pode ser vazio.")
        if self.count < 0 or self.uncertain_count < 0:
            raise InvalidEventMetricError("Contagens não podem ser negativas.")
        if self.uncertain_count > self.count:
            raise InvalidEventMetricError("uncertain_count não pode exceder count.")
        if self.duration_avg_ms is not None and self.duration_avg_ms < 0:
            raise InvalidEventMetricError("duration_avg_ms não pode ser negativo.")
