from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.exceptions import InvalidOccupancyMetricError
from src.domain.value_objects.time_window import TimeWindow


class DownsamplingService:
    """Consolida métricas de uma granularidade fina em uma métrica de granularidade mais grossa
    (rollup 1s -> 1m -> 1h)."""

    def rollup(
        self, metrics: list[OccupancyMetric], zone_id: str, target_window: TimeWindow
    ) -> OccupancyMetric:
        if not metrics:
            raise InvalidOccupancyMetricError("Não é possível consolidar uma lista vazia de métricas.")

        total_count = sum(metric.total_count for metric in metrics)
        occupancy_peak = max(metric.occupancy_peak for metric in metrics)
        dwell_time_avg = self._weighted_dwell_time_avg(metrics, total_count)

        return OccupancyMetric(
            zone_id=zone_id,
            window=target_window,
            dwell_time_avg=dwell_time_avg,
            occupancy_peak=occupancy_peak,
            total_count=total_count,
        )

    @staticmethod
    def _weighted_dwell_time_avg(metrics: list[OccupancyMetric], total_count: int) -> float:
        if total_count == 0:
            return sum(metric.dwell_time_avg for metric in metrics) / len(metrics)
        weighted_sum = sum(metric.dwell_time_avg * metric.total_count for metric in metrics)
        return weighted_sum / total_count
