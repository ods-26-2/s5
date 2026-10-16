from datetime import datetime

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.close_metric_windows_use_case import CloseMetricWindowsUseCase
from src.application.use_cases.handle_bus_message_use_case import HandleBusMessageUseCase
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.domain.services.aggregation_strategy import ZoneOccupancyAggregationStrategy
from src.domain.services.event_metrics_aggregation import EventMetricsAggregation
from src.domain.services.message_deduplicator import MessageDeduplicator
from src.infrastructure.b3_bus.b3_event_consumer import InMemoryB3EventConsumer
from src.infrastructure.b3_bus.s5_subscriptions import subscribe_s5
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.domain.value_objects.time_window import TimeWindow
from src.infrastructure.workers.metrics_window_worker import MetricsWindowWorker
from tests.fixtures.spec_examples import (
    REPLAY_SESSION_ID,
    in_session,
    replay_session_started,
    replay_state,
    zone_occupancy,
    zone_transition_exit,
)


def test_deve_ingerir_pelo_barramento_e_publicar_zone_metrics_no_mesmo_barramento():
    bus = InMemoryB3EventConsumer()
    buffer = MetricsBuffer()
    handler = HandleBusMessageUseCase(IngestEnvelopeUseCase(MessageDeduplicator()), buffer)
    rejected = []
    subscribe_s5(bus, handler, on_error=lambda message, error: rejected.append(error))
    received = []
    bus.subscribe("ods.s5.zone_metrics", received.append)
    bus.start()

    repository = DuckDBTimeSeriesRepository(":memory:")
    ticks = iter([datetime(2026, 9, 23, 14, 29, 30), datetime(2026, 9, 23, 14, 30, 3)])
    worker = MetricsWindowWorker(
        CloseMetricWindowsUseCase(
            buffer, ZoneOccupancyAggregationStrategy(), EventMetricsAggregation(),
            repository, bus, OutgoingEnvelopeFactory(), granularities=("1m",),
        ),
        clock=lambda: next(ticks),
    )

    worker.run()
    bus.publish("ods.s1.zone_transition", zone_transition_exit())
    bus.publish("ods.s1.zone_transition", zone_transition_exit())
    malformed = zone_occupancy()
    del malformed["session_id"]
    bus.publish("ods.s1.zone_occupancy", malformed)
    worker.run()

    assert len(rejected) == 1
    assert [m["payload"]["dwell_avg_s"] for m in received] == [8395]


def test_replay_pelo_barramento_publica_metricas_na_sessao_de_replay_com_o_tempo_da_gravacao():
    bus = InMemoryB3EventConsumer()
    buffer = MetricsBuffer()
    subscribe_s5(bus, HandleBusMessageUseCase(IngestEnvelopeUseCase(MessageDeduplicator()), buffer))
    received = []
    bus.subscribe("ods.s5.zone_metrics", received.append)
    bus.start()
    repository = DuckDBTimeSeriesRepository(":memory:")
    worker = MetricsWindowWorker(
        CloseMetricWindowsUseCase(
            buffer, ZoneOccupancyAggregationStrategy(), EventMetricsAggregation(),
            repository, bus, OutgoingEnvelopeFactory(), granularities=("1m",),
        ),
        clock=lambda: datetime(2026, 10, 16, 13, 0, 0),
    )

    bus.publish("ods.s1.zone_transition", in_session(zone_transition_exit(), REPLAY_SESSION_ID, "m-1"))
    bus.publish("ods.session.started", replay_session_started())
    bus.publish(
        "ods.p6.replay.state",
        in_session(replay_state(), REPLAY_SESSION_ID, "hb-1", "2026-09-23T14:30:03.000Z"),
    )
    worker.run()

    assert [(m["session_id"], m["payload"]["dwell_avg_s"]) for m in received] == [(REPLAY_SESSION_ID, 8395)]
    period = TimeWindow(start_time=datetime(2026, 9, 23, 14), end_time=datetime(2026, 9, 23, 15))
    assert repository.query_metrics("vaga-12", period, "1m") == []
    assert len(repository.query_metrics("vaga-12", period, "1m", mode="REPLAY")) == 1
