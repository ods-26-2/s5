from datetime import datetime, timedelta

import duckdb

from src.domain.entities.event_metric import EventMetric
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


def test_deve_persistir_e_consultar_metrica_por_tipo_de_evento_no_duckdb():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 23, 14, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))
    repository.save_event_metric(
        EventMetric(
            event_type="PPE_NON_COMPLIANT", window=window, count=4, uncertain_count=1,
            zone_id="galpao-solda", object_class="person", duration_avg_ms=12400,
        ),
        granularity="1h",
    )

    result = repository.query_event_metrics("PPE_NON_COMPLIANT", window, "1h")

    assert len(result) == 1
    assert result[0].count == 4
    assert result[0].uncertain_count == 1
    assert result[0].zone_id == "galpao-solda"
    assert result[0].duration_avg_ms == 12400


def test_consulta_padrao_le_so_live_para_que_replay_nao_duplique_o_historico():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 23, 14, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))
    live = OccupancyMetric(zone_id="vaga-12", window=window, dwell_time_avg=1.0, occupancy_peak=1, total_count=1)
    replay = OccupancyMetric(zone_id="vaga-12", window=window, dwell_time_avg=2.0, occupancy_peak=1, total_count=5)
    repository.save_occupancy_metric(live, "1m", mode="LIVE", session_id="s-live")
    repository.save_occupancy_metric(replay, "1m", mode="REPLAY", session_id="s-replay")
    period = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))

    assert [m.total_count for m in repository.query_metrics("vaga-12", period, "1m")] == [1]
    assert [m.total_count for m in repository.query_metrics("vaga-12", period, "1m", mode="REPLAY")] == [5]


def test_metricas_de_evento_em_replay_ficam_fora_da_consulta_padrao():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 23, 14, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))
    metric = EventMetric(event_type="PPE_NON_COMPLIANT", window=window, count=1, uncertain_count=0)
    repository.save_event_metric(metric, "1h", mode="REPLAY", session_id="s-replay")

    assert repository.query_event_metrics("PPE_NON_COMPLIANT", window, "1h") == []
    assert len(repository.query_event_metrics("PPE_NON_COMPLIANT", window, "1h", mode="REPLAY")) == 1


def test_deve_acrescentar_mode_e_session_id_em_event_metrics_criada_sem_elas(tmp_path):
    database_path = str(tmp_path / "passo3.db")
    legacy = duckdb.connect(database_path)
    legacy.execute(
        "CREATE TABLE event_metrics (event_type VARCHAR, zone_id VARCHAR, object_class VARCHAR,"
        " granularity VARCHAR, start_time TIMESTAMP, end_time TIMESTAMP, count INTEGER,"
        " uncertain_count INTEGER, duration_avg_ms INTEGER)"
    )
    base_time = datetime(2026, 9, 23, 14, 0, 0)
    legacy.execute(
        "INSERT INTO event_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ["X", None, None, "1h", base_time, base_time + timedelta(hours=1), 2, 0, None],
    )
    legacy.close()

    repository = DuckDBTimeSeriesRepository(database_path)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))

    assert [m.count for m in repository.query_event_metrics("X", window, "1h")] == [2]
