from datetime import datetime

from fastapi import APIRouter, Query

from src.application.dtos.heatmap_query_dto import HeatmapQueryDTO
from src.application.dtos.occupancy_metric_dto import OccupancyMetricDTO
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.value_objects.time_window import TimeWindow


def create_metrics_query_router(repository: ITimeSeriesRepository) -> APIRouter:
    """Expõe métricas de ocupação acumuladas e grades de mapa de calor via REST,
    consultando o repositório de séries temporais (S5.4) para a aplicação."""

    router = APIRouter(prefix="/api/v5")

    @router.get("/metrics/{zone_id}")
    def get_metrics(
        zone_id: str,
        start_time: datetime,
        end_time: datetime,
        granularity: str = Query(default="1m"),
    ) -> list[OccupancyMetricDTO]:
        window = TimeWindow(start_time=start_time, end_time=end_time)
        metrics = repository.query_metrics(zone_id, window, granularity)
        return [OccupancyMetricDTO.from_entity(metric) for metric in metrics]

    @router.get("/heatmaps/{grid_id}")
    def get_heatmap(grid_id: str, start_time: datetime, end_time: datetime) -> list[HeatmapQueryDTO]:
        window = TimeWindow(start_time=start_time, end_time=end_time)
        grids = repository.query_heatmap(grid_id, window)
        return [HeatmapQueryDTO.from_entity(grid) for grid in grids]

    return router
