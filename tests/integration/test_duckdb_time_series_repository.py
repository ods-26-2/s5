from datetime import datetime, timedelta

import duckdb

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.value_objects.time_window import TimeWindow
from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository


def test_deve_persistir_e_consultar_metrica_de_ocupacao_no_duckdb():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))
    metric = OccupancyMetric(
        zone_id="zone-01", window=window, dwell_time_avg=12.5, occupancy_peak=4, total_count=10,
        occupancy_avg=2.5,
    )

    repository.save_occupancy_metric(metric, granularity="1m")
    result = repository.query_metrics(
        "zone-01", TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1)), "1m"
    )

    assert len(result) == 1
    assert result[0].zone_id == "zone-01"
    assert result[0].total_count == 10
    assert result[0].occupancy_avg == 2.5


def test_deve_persistir_e_consultar_celulas_de_heatmap_no_duckdb():
    repository = DuckDBTimeSeriesRepository(":memory:")
    timestamp = datetime(2026, 9, 10, 10, 0, 0)
    grid = HeatmapGrid(
        grid_id="grid-01",
        cells=(SpatialCell(position=WorldCoordinate(x=1.0, y=2.0), density=0.8),),
    )

    repository.save_heatmap_grid(grid, timestamp)
    result = repository.query_heatmap(
        "grid-01", TimeWindow(start_time=timestamp - timedelta(seconds=1), end_time=timestamp + timedelta(seconds=1))
    )

    assert len(result) == 1
    assert result[0].cells[0].density == 0.8


def test_deve_retornar_lista_vazia_quando_nao_houver_metricas_na_janela():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    result = repository.query_metrics("zone-01", window, "1m")

    assert result == []


def test_deve_acrescentar_occupancy_avg_em_banco_criado_antes_da_coluna(tmp_path):
    database_path = str(tmp_path / "legado.db")
    legacy = duckdb.connect(database_path)
    legacy.execute(
        "CREATE TABLE occupancy_metrics (zone_id VARCHAR, granularity VARCHAR, start_time TIMESTAMP,"
        " end_time TIMESTAMP, dwell_time_avg DOUBLE, occupancy_peak INTEGER, total_count INTEGER)"
    )
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    legacy.execute(
        "INSERT INTO occupancy_metrics VALUES (?, ?, ?, ?, ?, ?, ?)",
        ["zone-01", "1m", base_time, base_time + timedelta(minutes=1), 3.0, 1, 2],
    )
    legacy.close()

    repository = DuckDBTimeSeriesRepository(database_path)
    result = repository.query_metrics(
        "zone-01", TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1)), "1m"
    )

    assert result[0].total_count == 2
    assert result[0].occupancy_avg == 0.0
