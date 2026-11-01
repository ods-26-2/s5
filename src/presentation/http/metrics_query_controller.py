from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from src.application.use_cases.query_heatmap_use_case import QueryHeatmapUseCase
from src.application.use_cases.query_metrics_use_case import UNKNOWN_ZONE, QueryMetricsUseCase
from src.domain.exceptions import QueryRejectedError
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository


def _payload(**params: object) -> dict:
    """Parâmetros de query string → payload da consulta do barramento, sem os ausentes."""
    return {name: value for name, value in params.items() if value is not None}


def _respond(run, payload: dict) -> JSONResponse:
    try:
        return JSONResponse({"status": "OK", **run(payload)})
    except QueryRejectedError as error:
        status_code = 404 if error.code == UNKNOWN_ZONE else 400
        body = {"status": "ERROR", "error": {"code": error.code, "message": error.message}}
        return JSONResponse(body, status_code=status_code)


def create_metrics_query_router(repository: ITimeSeriesRepository) -> APIRouter:
    """API REST de depuração. As aplicações consultam o S5 pelo barramento
    (ods.s5.metrics.query e ods.s5.heatmap.query); estas rotas executam os mesmos casos
    de uso, com os mesmos parâmetros, formato de resposta e códigos de erro, para
    inspecionar o banco durante o desenvolvimento."""

    router = APIRouter(prefix="/api/v5")
    query_metrics = QueryMetricsUseCase(repository)
    query_heatmap = QueryHeatmapUseCase(repository)

    @router.get("/metrics")
    def get_metrics(
        metric: str,
        period_start_at: str,
        period_end_at: str,
        granularity: str,
        zone_id: str | None = None,
        event_type: str | None = None,
        object_class: str | None = Query(default=None, alias="class"),
    ) -> JSONResponse:
        return _respond(
            query_metrics.execute,
            _payload(
                metric=metric,
                period_start_at=period_start_at,
                period_end_at=period_end_at,
                granularity=granularity,
                zone_id=zone_id,
                event_type=event_type,
                **{"class": object_class},
            ),
        )

    @router.get("/heatmap")
    def get_heatmap(
        period_start_at: str,
        period_end_at: str,
        space_id: str | None = None,
        cell_size_m: float | None = None,
        source_id: str | None = None,
        cell_size_px: float | None = None,
        object_class: str | None = Query(default=None, alias="class"),
    ) -> JSONResponse:
        return _respond(
            query_heatmap.execute,
            _payload(
                period_start_at=period_start_at,
                period_end_at=period_end_at,
                space_id=space_id,
                cell_size_m=cell_size_m,
                source_id=source_id,
                cell_size_px=cell_size_px,
                **{"class": object_class},
            ),
        )

    return router
