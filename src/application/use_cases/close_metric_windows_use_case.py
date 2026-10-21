from datetime import datetime, timedelta

from src.application.messaging.metric_payloads import event_metrics_payload, zone_metrics_payload
from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.ports.event_publisher import IEventPublisher
from src.application.state.metrics_buffer import MetricsBuffer
from src.domain.entities.session_start import REPLAY
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.aggregation_strategy import AggregationStrategy
from src.domain.services.event_metrics_aggregation import EventMetricsAggregation
from src.domain.value_objects.granularity import GRANULARITY_SECONDS, closed_windows
from src.domain.value_objects.time_window import TimeWindow

ZONE_METRICS_SCHEMA = "ods.s5.zone_metrics"
EVENT_METRICS_SCHEMA = "ods.s5.event_metrics"
DEFAULT_GRANULARITIES = ("1m", "15m", "1h", "1d")
DEFAULT_GRACE_SECONDS = 2.0


class CloseMetricWindowsUseCase:
    """A cada disparo, fecha as janelas alinhadas (1m, 15m, 1h, 1d) que terminaram desde o
    disparo anterior, persiste as métricas e publica ods.s5.zone_metrics (uma por zona
    conhecida) e ods.s5.event_metrics (uma por tipo de evento com ocorrência).

    O relógio depende do modo da sessão corrente: em LIVE é o relógio de parede (`now`);
    em REPLAY é o watermark de captura da gravação, porque o tempo de captura reproduzido
    não acompanha a parede e pode até voltar (SEEK, LOOP). Uma janela só fecha
    `grace_seconds` depois do seu fim, para acolher a latência entre captura e publicação.

    A cada nova sessão o cursor volta ao início dela: as janelas ainda abertas da sessão
    anterior são abandonadas, como o resto do estado daquela sessão.
    """

    def __init__(
        self,
        buffer: MetricsBuffer,
        zone_aggregation: AggregationStrategy,
        event_aggregation: EventMetricsAggregation,
        repository: ITimeSeriesRepository,
        publisher: IEventPublisher,
        envelope_factory: OutgoingEnvelopeFactory,
        granularities: tuple[str, ...] = DEFAULT_GRANULARITIES,
        grace_seconds: float = DEFAULT_GRACE_SECONDS,
    ) -> None:
        self._buffer = buffer
        self._zone_aggregation = zone_aggregation
        self._event_aggregation = event_aggregation
        self._repository = repository
        self._publisher = publisher
        self._envelope_factory = envelope_factory
        self._granularities = granularities
        self._grace = timedelta(seconds=grace_seconds)
        self._cursor_session_id: str | None = None
        self._closed_until: datetime | None = None

    def execute(self, now: datetime) -> list[dict]:
        session = self._buffer.session
        if session is None:
            return []
        if session.session_id != self._cursor_session_id:
            self._cursor_session_id = session.session_id
            self._closed_until = session.started_at

        clock = session.watermark if session.mode == REPLAY else now
        until = clock - self._grace
        if until <= self._closed_until:
            return []

        published = []
        for granularity in self._granularities:
            for window in closed_windows(granularity, self._closed_until, until):
                published += self._close_zone_window(granularity, window, session.session_id, session.mode)
                published += self._close_event_window(granularity, window, session.session_id, session.mode)

        self._persist_presence(session.session_id, until)
        self._closed_until = until
        longest = max(GRANULARITY_SECONDS[g] for g in self._granularities)
        self._buffer.prune(before=until - timedelta(seconds=longest))
        return published

    def _persist_presence(self, session_id: str, until: datetime) -> None:
        drained = self._buffer.presence.drain(session_id, until)
        if drained:
            self._repository.save_presence(
                [(key, seconds, self._buffer.mode_of(key.session_id)) for key, seconds in drained.items()]
            )

    def _close_zone_window(
        self, granularity: str, window: TimeWindow, session_id: str, mode: str
    ) -> list[dict]:
        messages = []
        for zone_id, context in sorted(self._buffer.zones.items()):
            metric = self._zone_aggregation.aggregate(
                self._buffer.transitions, self._buffer.samples, zone_id, window
            )
            self._repository.save_occupancy_metric(
                metric, granularity, mode=mode, session_id=session_id
            )
            messages.append(
                self._publish(
                    ZONE_METRICS_SCHEMA,
                    zone_metrics_payload(metric, granularity),
                    window.end_time,
                    session_id,
                    source_id=context.source_id,
                    artifact_version=context.artifact_version,
                )
            )
        return messages

    def _close_event_window(
        self, granularity: str, window: TimeWindow, session_id: str, mode: str
    ) -> list[dict]:
        messages = []
        for metric in self._event_aggregation.aggregate(self._buffer.events, window):
            self._repository.save_event_metric(
                metric, granularity, mode=mode, session_id=session_id
            )
            messages.append(
                self._publish(
                    EVENT_METRICS_SCHEMA,
                    event_metrics_payload(metric, granularity),
                    window.end_time,
                    session_id,
                    artifact_version=self._buffer.rules_versions.get(metric.event_type),
                )
            )
        return messages

    def _publish(
        self, schema: str, payload: dict, captured_at: datetime, session_id: str, **context: str | None
    ) -> dict:
        message = self._envelope_factory.service_event(
            schema, payload, captured_at=captured_at, session_id=session_id, **context
        )
        self._publisher.publish(schema, message)
        return message

