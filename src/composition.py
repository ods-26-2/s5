"""Raiz de composição: monta o S5 completo sobre um barramento e um repositório.

Fica fora das quatro camadas porque conhece todas elas. Trocar o barramento em memória
por um cliente de broker real (MQTT, NATS…) só exige passar outro objeto que implemente
B3EventConsumer e IEventPublisher.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.parsers.artifact_parser import parse_descriptor
from src.application.ports.artifact_source import IArtifactSource
from src.application.state.artifact_catalog import ArtifactCatalog
from src.application.ports.event_publisher import IEventPublisher
from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.answer_query_use_case import AnswerQueryUseCase
from src.application.use_cases.close_metric_windows_use_case import (
    DEFAULT_GRANULARITIES,
    CloseMetricWindowsUseCase,
)
from src.application.use_cases.handle_artifact_message_use_case import HandleArtifactMessageUseCase
from src.application.use_cases.handle_bus_message_use_case import HandleBusMessageUseCase
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.application.use_cases.load_artifact_use_case import LoadArtifactUseCase
from src.application.use_cases.purge_expired_data_use_case import PurgeExpiredDataUseCase
from src.application.use_cases.query_heatmap_use_case import QueryHeatmapUseCase
from src.application.use_cases.query_metrics_use_case import QueryMetricsUseCase
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.aggregation_strategy import ZoneOccupancyAggregationStrategy
from src.domain.services.event_metrics_aggregation import EventMetricsAggregation
from src.domain.services.message_deduplicator import MessageDeduplicator
from src.domain.value_objects.retention_policy import RetentionPolicy
from src.infrastructure.artifacts.file_artifact_source import FileArtifactSource
from src.infrastructure.b3_bus.b3_event_consumer import B3EventConsumer
from src.infrastructure.b3_bus.s5_subscriptions import SerializedHandler, subscribe_s5
from src.infrastructure.contracts.contract_validator import (
    ContractValidator,
    ValidatingPublisher,
    ViolationCallback,
)
from src.infrastructure.workers.metrics_window_worker import MetricsWindowWorker

METRICS_QUERY_SCHEMA = "ods.s5.metrics.query"
HEATMAP_QUERY_SCHEMA = "ods.s5.heatmap.query"


@dataclass(frozen=True)


class S5Service:
    """O S5 montado: o worker fecha as janelas, purge apaga o que expirou e o resto reage
    ao barramento. O chamador dispara os dois periodicamente."""

    buffer: MetricsBuffer
    worker: MetricsWindowWorker
    purge: PurgeExpiredDataUseCase
    catalog: ArtifactCatalog


def build_s5(
    bus: B3EventConsumer,
    publisher: IEventPublisher,
    repository: ITimeSeriesRepository,
    clock: Callable[[], datetime] | None = None,
    granularities: tuple[str, ...] = DEFAULT_GRANULARITIES,
    retention: RetentionPolicy | None = None,
    on_contract_violation: ViolationCallback | None = None,
    artifact_source: IArtifactSource | None = None,
    initial_artifacts: list[dict] = (),
) -> S5Service:
    """Assina os tópicos de entrada e de consulta e devolve o worker de fechamento de
    janelas (disparar a cada poucos segundos) e o expurgo (disparar a cada hora).

    Tudo o que o S5 publica passa pelo validador de contratos antes de chegar ao
    barramento. Mensagem fora do contrato é descartada e vai para `on_contract_violation`
    (por padrão, o log de erro); os testes passam uma função que lança a exceção.

    `initial_artifacts` são os descritores dos artefatos fixados na build (ZONES e
    CALIBRATION), carregados antes de qualquer assinatura: se um deles não carregar, o
    S5 não sobe, porque publicaria métricas sem as zonas que a aplicação definiu. Versões
    novas chegam depois por ods.artifact.published e ods.i3.calibration.
    """
    catalog = ArtifactCatalog()
    loader = LoadArtifactUseCase(artifact_source or FileArtifactSource(), catalog)
    for descriptor in initial_artifacts:
        loader.execute(parse_descriptor(descriptor))

    validator_options = {"on_violation": on_contract_violation} if on_contract_violation else {}
    publisher = ValidatingPublisher(publisher, ContractValidator(), **validator_options)
    factory = OutgoingEnvelopeFactory()
    buffer = MetricsBuffer()

    subscribe_s5(bus, HandleArtifactMessageUseCase(loader, catalog, MessageDeduplicator()))
    buffer_lock = threading.RLock()
    subscribe_s5(
        bus,
        SerializedHandler(
            HandleBusMessageUseCase(IngestEnvelopeUseCase(MessageDeduplicator()), buffer),
            buffer_lock,
        ),
    )
    subscribe_s5(
        bus,
        AnswerQueryUseCase(
            {
                METRICS_QUERY_SCHEMA: QueryMetricsUseCase(repository, catalog).execute,
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
        catalog=catalog,
    )
    clock_option = {"clock": clock} if clock else {}
    worker = MetricsWindowWorker(close_windows, lock=buffer_lock, **clock_option)
    purge = PurgeExpiredDataUseCase(repository, retention or RetentionPolicy())
    return S5Service(buffer=buffer, worker=worker, purge=purge, catalog=catalog)
