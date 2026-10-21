from datetime import datetime

from src.composition import build_s5
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


def test_s5_montado_pela_composicao_ingere_publica_e_responde_pelo_barramento():
    bus = InMemoryB3EventConsumer()
    ticks = iter([datetime(2026, 9, 23, 14, 29, 30), datetime(2026, 9, 23, 15, 0, 3)])
    service = build_s5(bus, bus, DuckDBTimeSeriesRepository(":memory:"), clock=lambda: next(ticks))
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
