from datetime import datetime

from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.domain.services.message_deduplicator import MessageDeduplicator
from tests.fixtures.spec_examples import (
    position,
    REPLAY_SESSION_ID,
    SESSION_ID,
    in_session,
    qualified_event,
    replay_session_started,
    replay_state,
    zone_occupancy,
    zone_transition_exit,
)


def _buffer() -> MetricsBuffer:
    buffer = MetricsBuffer()
    ingest = IngestEnvelopeUseCase(MessageDeduplicator())
    for message in (zone_transition_exit(), zone_occupancy(), qualified_event()):
        buffer.add(ingest.execute(message))
    return buffer


def test_deve_guardar_contexto_da_zona_e_versao_das_regras():
    buffer = _buffer()
    assert buffer.zones["vaga-12"].source_id == "cam0"
    assert buffer.zones["vaga-12"].artifact_version == "zones-a8-2"
    assert buffer.rules_versions["PPE_NON_COMPLIANT"] == "rules-a5-3"


def test_deve_descartar_antigos_mas_manter_ultima_amostra_de_cada_zona():
    buffer = _buffer()
    buffer.prune(before=datetime(2026, 9, 24))

    assert buffer.transitions == []
    assert [s.zone_id for s in buffer.samples] == ["vaga-12"]


def test_evento_sem_encerramento_e_sem_publicacao_recente_sai_do_buffer():
    buffer = _buffer()
    buffer.prune(before=datetime(2026, 9, 24))

    assert buffer.events == []


def test_evento_ativo_fica_inteiro_enquanto_tiver_publicacao_recente():
    ingest = _ingest()
    buffer = _buffer()
    update = qualified_event()
    update.update(message_id="m-update", captured_at="2026-09-24T10:00:00.000Z")
    update["payload"].update(phase="UPDATED", duration_ms=70_208_000)
    buffer.add(ingest.execute(update))

    buffer.prune(before=datetime(2026, 9, 24))

    assert [e.phase for e in buffer.events] == ["STARTED", "UPDATED"]


def _ingest():
    return IngestEnvelopeUseCase(MessageDeduplicator())


def test_deve_adotar_como_live_a_sessao_de_mensagem_que_chega_antes_do_anuncio():
    buffer = _buffer()
    assert buffer.session.session_id == SESSION_ID
    assert buffer.session.mode == "LIVE"
    assert buffer.session.started_at == datetime(2026, 9, 23, 14, 29, 59, 200000)
    assert buffer.session.watermark == datetime(2026, 9, 23, 14, 30)


def test_anuncio_da_sessao_ja_adotada_completa_modo_e_inicio_sem_descartar_dados():
    ingest = _ingest()
    buffer = MetricsBuffer()
    buffer.add(ingest.execute(in_session(zone_transition_exit(), REPLAY_SESSION_ID, "m-1")))

    buffer.add(ingest.execute(replay_session_started()))

    assert buffer.session.mode == "REPLAY"
    assert buffer.session.started_at == datetime(2026, 9, 23, 14, 29, 58)
    assert len(buffer.transitions) == 1


def test_nova_sessao_descarta_o_estado_da_anterior_e_ignora_mensagens_atrasadas_dela():
    ingest = _ingest()
    buffer = _buffer()

    buffer.add(ingest.execute(replay_session_started()))
    late = ingest.execute(in_session(zone_occupancy(), SESSION_ID, "m-atrasada"))

    assert buffer.add(late) is False
    assert buffer.transitions == [] and buffer.samples == [] and buffer.events == []
    assert buffer.session.session_id == REPLAY_SESSION_ID
    assert SESSION_ID in buffer.ended_sessions


def test_deve_marcar_previous_session_id_como_encerrada():
    buffer = MetricsBuffer()
    buffer.add(_ingest().execute(replay_session_started()))
    assert "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d" in buffer.ended_sessions


def test_replay_state_avanca_o_watermark_sem_guardar_mensagem():
    ingest = _ingest()
    buffer = MetricsBuffer()
    buffer.add(ingest.execute(replay_session_started()))

    buffer.add(ingest.execute(replay_state()))

    assert buffer.session.watermark == datetime(2026, 9, 23, 14, 29, 59)
    assert buffer.transitions == [] and buffer.samples == []


def test_posicoes_vao_para_o_acumulador_de_presenca():
    ingest = _ingest()
    buffer = MetricsBuffer()
    buffer.add(ingest.execute(position()))
    later = in_session(position(), SESSION_ID, "m-pos-2", "2026-09-23T14:30:00.370Z")
    buffer.add(ingest.execute(later))

    drained = buffer.presence.drain(SESSION_ID, datetime(2026, 9, 23, 14, 31))
    assert [round(v, 3) for v in drained.values()] == [0.5]


def test_modo_da_sessao_anunciada_e_lembrado_depois_que_ela_termina():
    ingest = _ingest()
    buffer = MetricsBuffer()
    buffer.add(ingest.execute(replay_session_started()))
    buffer.add(ingest.execute(zone_occupancy()))

    assert buffer.mode_of(REPLAY_SESSION_ID) == "REPLAY"
    assert buffer.mode_of(SESSION_ID) == "LIVE"
