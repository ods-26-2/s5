from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.services.presence_accumulator import METERS, PresenceKey
from src.domain.value_objects.time_window import TimeWindow
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router

BASE = datetime(2026, 9, 23, 14, 0, 0)
PERIOD = {"period_start_at": "2026-09-23T14:00:00.000Z", "period_end_at": "2026-09-23T15:00:00.000Z"}


def _client() -> TestClient:
    repository = DuckDBTimeSeriesRepository(":memory:")
    repository.save_occupancy_metric(
        OccupancyMetric(
            zone_id="vaga-12", window=TimeWindow(start_time=BASE, end_time=BASE + timedelta(minutes=15)),
            dwell_time_avg=1830.0, occupancy_peak=1, total_count=3, occupancy_avg=0.72,
        ),
        granularity="15m",
    )
    repository.save_presence([(PresenceKey("s-1", METERS, "patio-1", "person", 34, 71, BASE), 12.0, "LIVE")])
    app = FastAPI()
    app.include_router(create_metrics_query_router(repository))
    return TestClient(app)


def test_deve_devolver_a_serie_no_formato_de_ods_s5_zone_metrics():
    response = _client().get(
        "/api/v5/metrics", params={"metric": "ZONE", "zone_id": "vaga-12", "granularity": "15m", **PERIOD}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "series": [
            {
                "zone_id": "vaga-12",
                "window_start_at": "2026-09-23T14:00:00.000Z",
                "window_end_at": "2026-09-23T14:15:00.000Z",
                "granularity": "15m",
                "total_count": 3,
                "occupancy_peak": 1,
                "occupancy_avg": 0.72,
                "dwell_avg_s": 1830,
            }
        ],
    }


def test_deve_devolver_mapa_de_calor_no_formato_da_reply_do_barramento():
    response = _client().get(
        "/api/v5/heatmap", params={"space_id": "patio-1", "cell_size_m": 0.5, "class": "person", **PERIOD}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK", "grid_width": 1, "grid_height": 1, "cell_size_m": 0.5, "origin": [3.0, 7.0], "cells": [[12]],
    }


def test_zona_desconhecida_responde_404_com_o_codigo_do_contrato():
    response = _client().get(
        "/api/v5/metrics", params={"metric": "ZONE", "zone_id": "vaga-99", "granularity": "15m", **PERIOD}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_ZONE"


def test_consulta_invalida_responde_400():
    response = _client().get("/api/v5/metrics", params={"metric": "ZONE", "granularity": "5m", **PERIOD})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"
