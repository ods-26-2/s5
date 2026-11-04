from datetime import datetime
from pathlib import Path

import pytest

from src.composition import build_s5
from src.domain.exceptions import ArtifactUnavailableError
from src.infrastructure.artifacts.file_artifact_source import read_descriptor_files
from src.infrastructure.b3_bus.b3_event_consumer import InMemoryB3EventConsumer
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from tests.fixtures.spec_examples import (
    SESSION_ID,
    heatmap_query,
    in_session,
    metrics_query,
    position,
    qualified_event,
    zone_occupancy,
    zone_transition_exit,
)


def _fail(message, error):
    raise error


def test_s5_montado_pela_composicao_ingere_publica_e_responde_pelo_barramento():
    bus = InMemoryB3EventConsumer()
    ticks = iter([datetime(2026, 9, 23, 14, 29, 30), datetime(2026, 9, 23, 15, 0, 3)])
    service = build_s5(
        bus, bus, DuckDBTimeSeriesRepository(":memory:"), clock=lambda: next(ticks), on_contract_violation=_fail
    )
    published: dict[str, list[dict]] = {}
    for topic in ("ods.s5.zone_metrics", "ods.s5.event_metrics", "ods.s5.metrics.reply", "ods.s5.heatmap.reply"):
        bus.subscribe(topic, lambda message, topic=topic: published.setdefault(topic, []).append(message))
    bus.start()

    service.worker.run()
    bus.publish("ods.s1.zone_transition", zone_transition_exit())
    bus.publish("ods.s1.zone_occupancy", zone_occupancy())
    bus.publish("ods.s2.event", qualified_event())
    for message_id, captured_at in (
        ("p-1", "2026-09-23T14:29:59.870Z"),
        ("p-2", "2026-09-23T14:30:00.370Z"),
        ("p-3", "2026-09-23T14:30:00.870Z"),
    ):
        bus.publish("ods.s1.position", in_session(position(), SESSION_ID, message_id, captured_at))
    service.worker.run()
    query = metrics_query()
    query["payload"].update(
        period_start_at="2026-09-23T14:00:00.000Z", period_end_at="2026-09-23T15:00:00.000Z", granularity="1h"
    )
    bus.publish("ods.s5.metrics.query", query)
    bus.publish("ods.s5.heatmap.query", heatmap_query())

    assert {m["payload"]["granularity"] for m in published["ods.s5.zone_metrics"]} == {"1m", "15m", "1h"}
    assert [m["payload"]["count"] for m in published["ods.s5.event_metrics"] if m["payload"]["granularity"] == "1h"] == [1]
    [metrics_reply] = published["ods.s5.metrics.reply"]
    assert [item["dwell_avg_s"] for item in metrics_reply["payload"]["series"]] == [8395]
    [heatmap_reply] = published["ods.s5.heatmap.reply"]
    assert heatmap_reply["payload"]["origin"] == [3.0, 7.0]
    assert heatmap_reply["payload"]["cells"] == [[1]]


def test_s5_montado_pela_composicao_tem_expurgo_com_a_politica_padrao():
    bus = InMemoryB3EventConsumer()
    service = build_s5(bus, bus, DuckDBTimeSeriesRepository(":memory:"))

    removed = service.purge.execute(datetime(2026, 10, 21, 12))

    assert removed == {"metrics_1m": 0, "metrics_15m": 0, "metrics_1h": 0, "metrics_1d": 0, "presence": 0, "replay": 0}


def test_replies_de_erro_e_grade_vazia_tambem_seguem_o_contrato():
    bus = InMemoryB3EventConsumer()
    build_s5(bus, bus, DuckDBTimeSeriesRepository(":memory:"), on_contract_violation=_fail)
    replies = []
    bus.subscribe("ods.s5.metrics.reply", replies.append)
    bus.subscribe("ods.s5.heatmap.reply", replies.append)
    bus.start()

    bus.publish("ods.s5.metrics.query", metrics_query())  # zona sem métricas: UNKNOWN_ZONE
    bus.publish("ods.s5.heatmap.query", heatmap_query())  # sem presença: grade vazia
    invalid = heatmap_query()
    invalid["message_id"] = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
    invalid["payload"]["cell_size_m"] = 0.25
    bus.publish("ods.s5.heatmap.query", invalid)  # INVALID_QUERY

    assert [r["payload"]["status"] for r in replies] == ["ERROR", "OK", "ERROR"]


def test_s5_carrega_os_artefatos_da_build_e_recebe_versoes_novas_pelo_barramento():
    artifacts = Path(__file__).resolve().parents[1] / "fixtures" / "artifacts"
    bus = InMemoryB3EventConsumer()
    service = build_s5(
        bus, bus, DuckDBTimeSeriesRepository(":memory:"),
        initial_artifacts=read_descriptor_files([artifacts / "zones-a8-2.descriptor.json"]),
        on_contract_violation=_fail,
    )
    bus.start()
    assert service.catalog.versions() == {"zones-a8": "zones-a8-2"}

    [descriptor] = read_descriptor_files([artifacts / "cal-cam0-3.descriptor.json"])
    bus.publish("ods.artifact.published", {
        "message_type": "event", "message_id": "a1b2c3d4-0000-4000-8000-0000000000aa",
        "schema": "ods.artifact.published", "schema_version": "1.0", "producer": "I3",
        "published_at": "2026-09-23T14:00:00.000Z", "payload": descriptor,
    })

    assert service.catalog.versions() == {"zones-a8": "zones-a8-2", "cal-cam0": "cal-cam0-3"}


def test_s5_nao_sobe_se_um_artefato_da_build_nao_confere_com_o_hash(tmp_path):
    source = Path(__file__).resolve().parents[1] / "fixtures" / "artifacts"
    (tmp_path / "zones-a8-2.json").write_text("{}")
    (tmp_path / "zones-a8-2.descriptor.json").write_text((source / "zones-a8-2.descriptor.json").read_text())

    with pytest.raises(ArtifactUnavailableError):
        build_s5(
            InMemoryB3EventConsumer(), InMemoryB3EventConsumer(), DuckDBTimeSeriesRepository(":memory:"),
            initial_artifacts=read_descriptor_files([tmp_path / "zones-a8-2.descriptor.json"]),
        )


def test_reply_com_perfil_de_pico_segue_o_contrato_1_1():
    bus = InMemoryB3EventConsumer()
    build_s5(bus, bus, DuckDBTimeSeriesRepository(":memory:"), on_contract_violation=_fail)
    replies = []
    bus.subscribe("ods.s5.metrics.reply", replies.append)
    bus.start()
    query = metrics_query()
    query["payload"].update(metric="EVENT", profile="DAY_OF_WEEK", timezone="America/Sao_Paulo")
    del query["payload"]["zone_id"]

    bus.publish("ods.s5.metrics.query", query)

    [reply] = replies
    assert reply["schema_version"] == "1.1"
    assert reply["payload"]["profile"] == {
        "by": "DAY_OF_WEEK", "timezone": "America/Sao_Paulo", "peak_bucket": None, "buckets": [],
    }
