from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.time_window import TimeWindow


class ITimeSeriesRepository(ABC):
    """Contrato de persistência de séries temporais, isolando o domínio do DuckDB."""

    @abstractmethod
    def save_occupancy_metric(self, metric: OccupancyMetric, granularity: str) -> None: ...

    @abstractmethod
    def save_heatmap_grid(self, grid: HeatmapGrid, timestamp: datetime) -> None: ...

    @abstractmethod
    def query_metrics(
        self, zone_id: str, window: TimeWindow, granularity: str
    ) -> list[OccupancyMetric]: ...

    @abstractmethod
    def query_heatmap(self, grid_id: str, window: TimeWindow) -> list[HeatmapGrid]: ...
