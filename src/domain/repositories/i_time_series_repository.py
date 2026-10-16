from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.entities.session_start import LIVE
from src.domain.value_objects.time_window import TimeWindow


class ITimeSeriesRepository(ABC):
    """Contrato de persistência de séries temporais, isolando o domínio do DuckDB.

    Cada métrica é gravada com o modo (LIVE ou REPLAY) e a sessão que a produziram. Um
    replay reproduz o tempo de captura original, então as janelas dele coincidem com as
    da captura ao vivo daquele dia; as consultas leem só LIVE salvo pedido explícito,
    para que um replay não duplique o histórico.
    """

    @abstractmethod
    def save_occupancy_metric(
        self,
        metric: OccupancyMetric,
        granularity: str,
        mode: str = LIVE,
        session_id: str | None = None,
    ) -> None: ...

    @abstractmethod
    def save_event_metric(
        self,
        metric: EventMetric,
        granularity: str,
        mode: str = LIVE,
        session_id: str | None = None,
    ) -> None: ...

    @abstractmethod
    def save_heatmap_grid(self, grid: HeatmapGrid, timestamp: datetime) -> None: ...

    @abstractmethod
    def query_metrics(
        self, zone_id: str, window: TimeWindow, granularity: str, mode: str = LIVE
    ) -> list[OccupancyMetric]: ...

    @abstractmethod
    def query_heatmap(self, grid_id: str, window: TimeWindow) -> list[HeatmapGrid]: ...
