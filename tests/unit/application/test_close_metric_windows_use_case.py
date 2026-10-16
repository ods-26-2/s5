from datetime import datetime, timedelta

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.close_metric_windows_use_case import CloseMetricWindowsUseCase
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.application.ports.event_publisher import IEventPublisher
from src.domain.services.aggregation_strategy import ZoneOccupancyAggregationStrategy
from src.domain.services.event_metrics_aggregation import EventMetricsAggregation
from src.domain.services.message_deduplicator import MessageDeduplicator
from src.domain.entities.session_start import REPLAY
from tests.fixtures.spec_examples import (
    REPLAY_SESSION_ID,
    SESSION_ID,
    in_session,
    qualified_event,
    replay_session_started,
    replay_state,
    zone_occupancy,
    zone_transition_exit,
)

from .fakes import FakeTimeSeriesRepository


class RecordingPublisher(IEventPublisher):
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    def publish(self, topic: str, message: dict) -> None:
        self.published.append((topic, message))


def _setup(granularities=("1m",)):
    buffer = MetricsBuffer()
    ingest = IngestEnvelopeUseCase(MessageDeduplicator())
    for message in (zone_transition_exit(), zone_occupancy(), qualified_event()):
        buffer.add(ingest.execute(message))
    repository = FakeTimeSeriesRepository()
    publisher = RecordingPublisher()
    use_case = CloseMetricWindowsUseCase(
        buffer, ZoneOccupancyAggregationStrategy(), EventMetricsAggregation(),
        repository, publisher, OutgoingEnvelopeFactory(), granularities=granularities,
    )
    return use_case, repository, publisher


def _payloads(publisher, schema):
    return [message["payload"] for topic, message in publisher.published if topic == schema]


def test_primeiro_disparo_so_marca_o_ponto_de_partida():
    use_case, _, publisher = _setup()
    assert use_case.execute(datetime(2026, 9, 23, 14, 29, 30)) == []
    assert publisher.published == []


def test_deve_publicar_zone_metrics_da_janela_fechada_com_envelope_ev_servico():
    use_case, repository, publisher = _setup()
    use_case.execute(datetime(2026, 9, 23, 14, 29, 30))

    use_case.execute(datetime(2026, 9, 23, 14, 30, 3))

    [(topic, message)] = [p for p in publisher.published if p[0] == "ods.s5.zone_metrics"]
    assert message["producer"] == "S5"
    assert message["session_id"] == SESSION_ID
    assert message["source_id"] == "cam0"
    assert message["artifact_version"] == "zones-a8-2"
    assert message["captured_at"] == "2026-09-23T14:30:00.000Z"
    assert message["payload"] == {
        "zone_id": "vaga-12",
        "window_start_at": "2026-09-23T14:29:00.000Z",
        "window_end_at": "2026-09-23T14:30:00.000Z",
        "granularity": "1m",
        "total_count": 0,
        "occupancy_peak": 0,
        "occupancy_avg": 0.0,
        "dwell_avg_s": 8395,
    }
    assert repository.saved_metrics[0][1] == "1m"


def test_deve_publicar_event_metrics_com_versao_das_regras():
    use_case, repository, publisher = _setup(granularities=("1h",))
    use_case.execute(datetime(2026, 9, 23, 14, 59, 0))

    use_case.execute(datetime(2026, 9, 23, 15, 0, 3))

    [message] = [m for t, m in publisher.published if t == "ods.s5.event_metrics"]
    assert message["artifact_version"] == "rules-a5-3"
    assert message["payload"] == {
        "event_type": "PPE_NON_COMPLIANT",
        "zone_id": "galpao-solda",
        "class": "person",
        "window_start_at": "2026-09-23T14:00:00.000Z",
        "window_end_at": "2026-09-23T15:00:00.000Z",
        "granularity": "1h",
        "count": 1,
        "uncertain_count": 0,
    }
    assert repository.saved_event_metrics[0][1] == "1h"


def test_nao_deve_fechar_janela_antes_da_tolerancia():
    use_case, _, publisher = _setup()
    use_case.execute(datetime(2026, 9, 23, 14, 29, 30))

    assert use_case.execute(datetime(2026, 9, 23, 14, 30, 1)) == []


def test_nao_deve_publicar_a_mesma_janela_duas_vezes():
    use_case, _, publisher = _setup()
    use_case.execute(datetime(2026, 9, 23, 14, 29, 30))
    use_case.execute(datetime(2026, 9, 23, 14, 30, 3))

    assert use_case.execute(datetime(2026, 9, 23, 14, 30, 10)) == []


def test_deve_fechar_todas_as_janelas_perdidas_entre_disparos():
    use_case, _, publisher = _setup()
    use_case.execute(datetime(2026, 9, 23, 14, 29, 30))

    use_case.execute(datetime(2026, 9, 23, 14, 33, 3))

    ends = [p["window_end_at"] for p in _payloads(publisher, "ods.s5.zone_metrics")]
    assert ends == [f"2026-09-23T14:{m}:00.000Z" for m in (30, 31, 32, 33)]


def test_nao_deve_publicar_sem_nenhuma_mensagem_recebida():
    publisher = RecordingPublisher()
    use_case = CloseMetricWindowsUseCase(
        MetricsBuffer(), ZoneOccupancyAggregationStrategy(), EventMetricsAggregation(),
        FakeTimeSeriesRepository(), publisher, OutgoingEnvelopeFactory(),
    )
    use_case.execute(datetime(2026, 9, 23, 14, 0))

    assert use_case.execute(datetime(2026, 9, 23, 15, 0)) == []

WALL_CLOCK = datetime(2026, 10, 16, 13, 0, 0)


def _replay_setup():
    ingest = IngestEnvelopeUseCase(MessageDeduplicator())
    buffer = MetricsBuffer()
    buffer.add(ingest.execute(replay_session_started()))
    buffer.add(ingest.execute(in_session(zone_transition_exit(), REPLAY_SESSION_ID, "m-exit")))
    repository = FakeTimeSeriesRepository()
    publisher = RecordingPublisher()
    use_case = CloseMetricWindowsUseCase(
        buffer, ZoneOccupancyAggregationStrategy(), EventMetricsAggregation(),
        repository, publisher, OutgoingEnvelopeFactory(), granularities=("1m",),
    )
    return use_case, ingest, buffer, repository, publisher


def _heartbeat(ingest, buffer, captured_at: str, message_id: str):
    buffer.add(ingest.execute(in_session(replay_state(), REPLAY_SESSION_ID, message_id, captured_at)))


def test_em_replay_o_relogio_e_o_watermark_da_gravacao_e_nao_a_parede():
    use_case, ingest, buffer, repository, publisher = _replay_setup()
    assert use_case.execute(WALL_CLOCK) == []

    _heartbeat(ingest, buffer, "2026-09-23T14:30:02.500Z", "hb-1")
    published = use_case.execute(WALL_CLOCK)

    assert [m["payload"]["window_end_at"] for m in published] == ["2026-09-23T14:30:00.000Z"]
    assert published[0]["session_id"] == REPLAY_SESSION_ID
    assert repository.saved_modes == [(REPLAY, REPLAY_SESSION_ID)]


def test_replay_pausado_nao_fecha_janelas_mesmo_com_a_parede_andando():
    use_case, ingest, buffer, _, _ = _replay_setup()
    _heartbeat(ingest, buffer, "2026-09-23T14:29:59.000Z", "hb-1")

    assert use_case.execute(WALL_CLOCK + timedelta(hours=1)) == []


def test_nova_sessao_volta_o_cursor_ao_inicio_dela_e_abandona_janelas_abertas():
    use_case, ingest, buffer, _, publisher = _replay_setup()
    _heartbeat(ingest, buffer, "2026-09-23T14:30:02.500Z", "hb-1")
    use_case.execute(WALL_CLOCK)

    loop = replay_session_started()
    loop.update(message_id="m-loop", session_id="loop-2", captured_at="2026-09-23T14:20:00.000Z")
    loop["payload"].update(started_at="2026-09-23T14:20:00.000Z", reason="LOOP", previous_session_id=REPLAY_SESSION_ID)
    buffer.add(ingest.execute(loop))
    buffer.add(ingest.execute(in_session(replay_state(), "loop-2", "hb-2", "2026-09-23T14:21:02.500Z")))
    published = use_case.execute(WALL_CLOCK)

    assert [m["payload"]["window_end_at"] for m in published] == ["2026-09-23T14:21:00.000Z"]
    assert published[0]["session_id"] == "loop-2"
    assert published[0]["sequence"] == 0
    assert published[0]["payload"]["dwell_avg_s"] == 0
