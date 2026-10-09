from dataclasses import dataclass

from src.domain.entities.occupancy_metric import OccupancyMetric


@dataclass(frozen=True)
class OccupancyMetricDTO:
    """Representação de transporte da métrica de ocupação acumulada, para application/presentation."""

    zone_id: str
    dwell_time_avg: float
    occupancy_peak: int
    total_count: int

    @staticmethod
    def from_entity(metric: OccupancyMetric) -> "OccupancyMetricDTO":
        return OccupancyMetricDTO(
            zone_id=metric.zone_id,
            dwell_time_avg=metric.dwell_time_avg,
            occupancy_peak=metric.occupancy_peak,
            total_count=metric.total_count,
        )
