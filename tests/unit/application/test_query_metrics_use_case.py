import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.application.parsers.artifact_parser import parse_zones
from src.application.state.artifact_catalog import ArtifactCatalog
from src.application.use_cases.query_metrics_use_case import QueryMetricsUseCase
from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.exceptions import QueryRejectedError
from src.domain.value_objects.time_window import TimeWindow
from tests.fixtures.spec_examples import metrics_query

from .fakes import FakeTimeSeriesRepository


DAY = datetime(2026, 9, 22)
import json
from pathlib import Path

from src.application.parsers.artifact_parser import parse_zones
from src.application.state.artifact_catalog import ArtifactCatalog


def _repository() -> FakeTimeSeriesRepository:
    repository = FakeTimeSeriesRepository()
    for hour in range(2):
        window = TimeWindow(start_time=DAY + timedelta(hours=hour), end_time=DAY + timedelta(hours=hour + 1))
        repository.save_occupancy_metric(
            OccupancyMetric(zone_id="vaga-12", window=window, dwell_time_avg=1830.4,
                            occupancy_peak=1, total_count=3, occupancy_avg=0.72),
            "1h",
        )
    repository.save_event_metric(
        EventMetric(event_type="PPE_NON_COMPLIANT", window=TimeWindow(start_time=DAY, end_time=DAY + timedelta(hours=1)),
                    count=4, uncertain_count=1, zone_id="galpao-solda", object_class="person", duration_avg_ms=12400),
        "1h",
    )
    return repository


def _rejected_code(payload: dict) -> str:
    with pytest.raises(QueryRejectedError) as error:
        QueryMetricsUseCase(_repository()).execute(payload)
    return error.value.code


def test_deve_devolver_serie_por_zona_do_exemplo_da_especificacao():
    reply = QueryMetricsUseCase(_repository()).execute(metrics_query()["payload"])

    assert [item["window_start_at"] for item in reply["series"]] == [
        "2026-09-22T00:00:00.000Z", "2026-09-22T01:00:00.000Z",
    ]
    assert reply["series"][0] == {
        "zone_id": "vaga-12",
        "window_start_at": "2026-09-22T00:00:00.000Z",
        "window_end_at": "2026-09-22T01:00:00.000Z",
        "granularity": "1h",
        "total_count": 3,
        "occupancy_peak": 1,
        "occupancy_avg": 0.72,
        "dwell_avg_s": 1830,
    }


def test_deve_devolver_serie_por_tipo_de_evento():
    payload = metrics_query()["payload"]
    payload.update(metric="EVENT", event_type="PPE_NON_COMPLIANT")
    del payload["zone_id"]

    [item] = QueryMetricsUseCase(_repository()).execute(payload)["series"]
    assert item["count"] == 4 and item["uncertain_count"] == 1 and item["duration_avg_ms"] == 12400


def test_deve_recusar_zona_sem_metricas():
    payload = metrics_query()["payload"]
    payload["zone_id"] = "vaga-99"
    assert _rejected_code(payload) == "UNKNOWN_ZONE"


def test_deve_recusar_periodo_com_mais_de_1000_janelas():
    payload = metrics_query()["payload"]
    payload.update(granularity="1m", period_end_at="2026-09-23T00:00:00.000Z")  # 1440 janelas
    assert _rejected_code(payload) == "PERIOD_TOO_LONG"


@pytest.mark.parametrize(
    "change",
    [
        {"metric": "ALL"},
        {"granularity": "5m"},
        {"period_start_at": "ontem"},
        {"period_end_at": "2026-09-21T00:00:00.000Z"},
        {"event_type": "PPE_NON_COMPLIANT"},
    ],
)
def test_deve_recusar_consulta_invalida(change):
    payload = metrics_query()["payload"]
    payload.update(change)
    assert _rejected_code(payload) == "INVALID_QUERY"


def test_zona_do_artefato_sem_metricas_ainda_nao_e_desconhecida_e_serie_traz_space_id():
    content = json.loads((Path(__file__).resolve().parents[2] / "fixtures/artifacts/zones-a8-2.json").read_text())
    catalog = ArtifactCatalog()
    catalog.put_zones(parse_zones(content, "zones-a8", "zones-a8-2"))
    use_case = QueryMetricsUseCase(_repository(), catalog)

    payload = metrics_query()["payload"]
    payload["zone_id"] = "vaga-13"
    assert use_case.execute(payload) == {"series": []}

    series = use_case.execute(metrics_query()["payload"])["series"]
    assert {item["space_id"] for item in series} == {"patio-1"}


def test_perfil_por_hora_do_dia_no_fuso_pedido():
    payload = metrics_query()["payload"]
    payload.update(profile="HOUR_OF_DAY", timezone="America/Sao_Paulo")

    reply = QueryMetricsUseCase(_repository()).execute(payload)

    profile = reply["profile"]
    assert len(reply["series"]) == 2
    assert profile["by"] == "HOUR_OF_DAY" and profile["timezone"] == "America/Sao_Paulo"
    # As janelas de 00h e 01h UTC de 22/9 são 21h e 22h de 21/9 em São Paulo.
    assert [b["bucket"] for b in profile["buckets"]] == [21, 22]
    assert profile["buckets"][0] == {
        "bucket": 21, "windows": 1, "total_count": 3, "occupancy_peak": 1, "occupancy_avg": 0.72,
    }
    assert profile["peak_bucket"] == 21


def test_perfil_de_eventos_por_dia_da_semana_em_utc_por_padrao():
    payload = metrics_query()["payload"]
    payload.update(metric="EVENT", profile="DAY_OF_WEEK")
    del payload["zone_id"]

    profile = QueryMetricsUseCase(_repository()).execute(payload)["profile"]

    assert profile["timezone"] == "UTC"
    assert profile["buckets"] == [{"bucket": 2, "windows": 1, "count": 4, "uncertain_count": 1}]
    assert profile["peak_bucket"] == 2


def test_sem_profile_a_reply_e_a_da_versao_1_0():
    assert set(QueryMetricsUseCase(_repository()).execute(metrics_query()["payload"])) == {"series"}


@pytest.mark.parametrize(
    "change",
    [
        {"profile": "HOUR_OF_WEEK"},
        {"profile": "HOUR_OF_DAY", "granularity": "1d", "period_end_at": "2026-12-01T00:00:00.000Z"},
        {"profile": "DAY_OF_WEEK", "timezone": "Lua/Base_Alfa"},
    ],
)
def test_perfil_invalido_e_recusado(change):
    payload = metrics_query()["payload"]
    payload.update(change)
    assert _rejected_code(payload) == "INVALID_QUERY"
