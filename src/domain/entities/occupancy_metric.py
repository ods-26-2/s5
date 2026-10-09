from dataclasses import dataclass

from src.domain.exceptions import InvalidOccupancyMetricError
from src.domain.value_objects.time_window import TimeWindow


@dataclass(frozen=True)
class OccupancyMetric:
    """Métrica de ocupação acumulada de uma zona em uma janela de tempo."""

    zone_id: str
    window: TimeWindow
    dwell_time_avg: float
    occupancy_peak: int
    total_count: int

    def __post_init__(self) -> None:
        if not self.zone_id.strip():
            raise InvalidOccupancyMetricError("zone_id não pode ser vazio.")
        if self.dwell_time_avg < 0:
            raise InvalidOccupancyMetricError("dwell_time_avg não pode ser negativo.")
        if self.occupancy_peak < 0:
            raise InvalidOccupancyMetricError("occupancy_peak não pode ser negativo.")
        if self.total_count < 0:
            raise InvalidOccupancyMetricError("total_count não pode ser negativo.")
