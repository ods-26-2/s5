from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.value_objects.time_window import TimeWindow
from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router


def _build_client(repository: DuckDBTimeSeriesRepository) -> TestClient:
    app = FastAPI()
    app.include_router(create_metrics_query_router(repository))
    return TestClient(app)


def test_deve_retornar_metricas_da_zona_no_periodo_informado():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))
    repository.save_occupancy_metric(
        OccupancyMetric(
            zone_id="zone-01", window=window, dwell_time_avg=12.5, occupancy_peak=4, total_count=10
        ),
        granularity="1m",
    )
    client = _build_client(repository)

    response = client.get(
        "/api/v5/metrics/zone-01",
        params={
            "start_time": base_time.isoformat(),
            "end_time": (base_time + timedelta(hours=1)).isoformat(),
            "granularity": "1m",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["zone_id"] == "zone-01"
    assert body[0]["total_count"] == 10


def test_deve_retornar_heatmap_do_grid_no_periodo_informado():
    repository = DuckDBTimeSeriesRepository(":memory:")
    timestamp = datetime(2026, 9, 10, 10, 0, 0)
    repository.save_heatmap_grid(
        HeatmapGrid(
            grid_id="grid-01",
            cells=(SpatialCell(position=WorldCoordinate(x=1.0, y=2.0), density=0.8),),
        ),
        timestamp,
    )
    client = _build_client(repository)

    response = client.get(
        "/api/v5/heatmaps/grid-01",
        params={
            "start_time": (timestamp - timedelta(seconds=1)).isoformat(),
            "end_time": (timestamp + timedelta(seconds=1)).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["grid_id"] == "grid-01"
