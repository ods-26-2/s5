from datetime import datetime, timedelta

import duckdb

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.services.presence_accumulator import PresenceKey
from src.domain.value_objects.time_window import TimeWindow
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
    hour = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))
    result = repository.query_zone_series(hour, "1m", zone_id="zone-01")

    assert len(result) == 1
    assert result[0].zone_id == "zone-01"
    assert result[0].total_count == 10
    assert result[0].occupancy_avg == 2.5


def test_deve_retornar_lista_vazia_quando_nao_houver_metricas_na_janela():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    result = repository.query_zone_series(window, "1m", zone_id="zone-01")

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
    hour = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))
    result = repository.query_zone_series(hour, "1m", zone_id="zone-01")

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

    result = repository.query_event_series(window, "1h", event_type="PPE_NON_COMPLIANT")

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

    assert [m.total_count for m in repository.query_zone_series(period, "1m", zone_id="vaga-12")] == [1]
    assert [m.total_count for m in repository.query_zone_series(period, "1m", zone_id="vaga-12", mode="REPLAY")] == [5]


def test_metricas_de_evento_em_replay_ficam_fora_da_consulta_padrao():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 23, 14, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))
    metric = EventMetric(event_type="PPE_NON_COMPLIANT", window=window, count=1, uncertain_count=0)
    repository.save_event_metric(metric, "1h", mode="REPLAY", session_id="s-replay")

    assert repository.query_event_series(window, "1h", event_type="PPE_NON_COMPLIANT") == []
    assert len(repository.query_event_series(window, "1h", event_type="PPE_NON_COMPLIANT", mode="REPLAY")) == 1


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

    assert [m.count for m in repository.query_event_series(window, "1h", event_type="X")] == [2]


def test_deve_somar_presenca_por_celula_fina_no_periodo_filtrando_classe_e_modo():
    repository = DuckDBTimeSeriesRepository(":memory:")
    bucket = datetime(2026, 9, 23, 14, 10)

    def key(object_class="person", minute=0, session="s-1"):
        return PresenceKey(session, "METERS", "patio-1", object_class, 34, 71, bucket + timedelta(minutes=minute))

    repository.save_presence([
        (key(), 2.0, "LIVE"),
        (key(minute=1), 3.5, "LIVE"),
        (key(object_class="vehicle"), 9.0, "LIVE"),
        (key(session="s-replay"), 7.0, "REPLAY"),
        (key(minute=60), 1.0, "LIVE"),
    ])
    hour = TimeWindow(start_time=datetime(2026, 9, 23, 14), end_time=datetime(2026, 9, 23, 15))

    assert repository.query_presence("METERS", "patio-1", hour, object_class="person") == [(34, 71, 5.5)]
    assert repository.query_presence("METERS", "patio-1", hour) == [(34, 71, 14.5)]
    assert repository.query_presence("METERS", "patio-1", hour, mode="REPLAY") == [(34, 71, 7.0)]


def test_deve_consultar_series_com_filtros_opcionais():
    repository = DuckDBTimeSeriesRepository(":memory:")
    base_time = datetime(2026, 9, 23, 14, 0, 0)
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(hours=1))
    for zone_id in ("vaga-12", "vaga-13"):
        repository.save_occupancy_metric(
            OccupancyMetric(zone_id=zone_id, window=window, dwell_time_avg=1.0, occupancy_peak=1, total_count=1), "1h"
        )
    repository.save_event_metric(EventMetric(event_type="A", window=window, count=1, uncertain_count=0, zone_id="z"), "1h")
    repository.save_event_metric(EventMetric(event_type="B", window=window, count=2, uncertain_count=0), "1h")
    day = TimeWindow(start_time=base_time, end_time=base_time + timedelta(days=1))

    assert [m.zone_id for m in repository.query_zone_series(day, "1h")] == ["vaga-12", "vaga-13"]
    assert [m.zone_id for m in repository.query_zone_series(day, "1h", zone_id="vaga-13")] == ["vaga-13"]
    assert [m.event_type for m in repository.query_event_series(day, "1h")] == ["A", "B"]
    assert [m.count for m in repository.query_event_series(day, "1h", zone_id="z")] == [1]
    assert repository.zone_exists("vaga-12") and not repository.zone_exists("vaga-99")
