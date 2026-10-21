from datetime import datetime, timedelta

import pytest

from src.application.use_cases.query_metrics_use_case import QueryMetricsUseCase
from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.exceptions import QueryRejectedError
from src.domain.value_objects.time_window import TimeWindow
from tests.fixtures.spec_examples import metrics_query

from .fakes import FakeTimeSeriesRepository

DAY = datetime(2026, 9, 22)


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
