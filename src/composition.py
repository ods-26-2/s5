"""Raiz de composição: monta o S5 completo sobre um barramento e um repositório.

Fica fora das quatro camadas porque conhece todas elas. Trocar o barramento em memória
por um cliente de broker real (MQTT, NATS…) só exige passar outro objeto que implemente
B3EventConsumer e IEventPublisher.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.ports.event_publisher import IEventPublisher
from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.answer_query_use_case import AnswerQueryUseCase
from src.application.use_cases.close_metric_windows_use_case import (
    DEFAULT_GRANULARITIES,
    CloseMetricWindowsUseCase,
)
from src.application.use_cases.handle_bus_message_use_case import HandleBusMessageUseCase
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.application.use_cases.query_heatmap_use_case import QueryHeatmapUseCase
from src.application.use_cases.query_metrics_use_case import QueryMetricsUseCase
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.aggregation_strategy import ZoneOccupancyAggregationStrategy
from src.domain.services.event_metrics_aggregation import EventMetricsAggregation
from src.domain.services.message_deduplicator import MessageDeduplicator
from src.infrastructure.b3_bus.b3_event_consumer import B3EventConsumer
from src.infrastructure.b3_bus.s5_subscriptions import subscribe_s5
from src.infrastructure.workers.metrics_window_worker import MetricsWindowWorker

METRICS_QUERY_SCHEMA = "ods.s5.metrics.query"
HEATMAP_QUERY_SCHEMA = "ods.s5.heatmap.query"


@dataclass(frozen=True)


class S5Service:
    """O S5 montado: o worker fecha as janelas; o resto reage ao barramento."""

    buffer: MetricsBuffer
    worker: MetricsWindowWorker


def build_s5(
    bus: B3EventConsumer,
    publisher: IEventPublisher,
    repository: ITimeSeriesRepository,
    clock: Callable[[], datetime] | None = None,
    granularities: tuple[str, ...] = DEFAULT_GRANULARITIES,
) -> S5Service:
    """Assina os tópicos de entrada e de consulta e devolve o worker de fechamento de
    janelas, que o chamador dispara periodicamente (ex.: a cada 5 s)."""
    factory = OutgoingEnvelopeFactory()
    buffer = MetricsBuffer()

    subscribe_s5(bus, HandleBusMessageUseCase(IngestEnvelopeUseCase(MessageDeduplicator()), buffer))
    subscribe_s5(
        bus,
        AnswerQueryUseCase(
            {
                METRICS_QUERY_SCHEMA: QueryMetricsUseCase(repository).execute,
                HEATMAP_QUERY_SCHEMA: QueryHeatmapUseCase(repository).execute,
            },
            factory,
            publisher,
        ),
    )
    close_windows = CloseMetricWindowsUseCase(
        buffer,
        ZoneOccupancyAggregationStrategy(),
        EventMetricsAggregation(),
        repository,
        publisher,
        factory,
        granularities=granularities,
    )
    worker = MetricsWindowWorker(close_windows, clock) if clock else MetricsWindowWorker(close_windows)
    return S5Service(buffer=buffer, worker=worker)
