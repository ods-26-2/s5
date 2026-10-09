from datetime import datetime

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.value_objects.time_window import TimeWindow


class FakeTimeSeriesRepository(ITimeSeriesRepository):
    """Repositório em memória para testar casos de uso sem I/O real."""

    def __init__(self) -> None:
        self.saved_metrics: list[tuple[OccupancyMetric, str]] = []
        self.saved_heatmaps: list[tuple[HeatmapGrid, datetime]] = []
        self.metrics_to_return: list[OccupancyMetric] = []

    def save_occupancy_metric(self, metric: OccupancyMetric, granularity: str) -> None:
        self.saved_metrics.append((metric, granularity))

    def save_heatmap_grid(self, grid: HeatmapGrid, timestamp: datetime) -> None:
        self.saved_heatmaps.append((grid, timestamp))

    def query_metrics(
        self, zone_id: str, window: TimeWindow, granularity: str
    ) -> list[OccupancyMetric]:
        return self.metrics_to_return

    def query_heatmap(self, grid_id: str, window: TimeWindow) -> list[HeatmapGrid]:
        return [grid for grid, _ in self.saved_heatmaps if grid.grid_id == grid_id]
