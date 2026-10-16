from datetime import datetime

import pytest

from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.domain.entities.qualified_event import QualifiedEvent
from src.domain.entities.replay_state import ReplayState
from src.domain.entities.session_start import SessionStart
from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ZoneTransition
from src.domain.exceptions import (
    MalformedEventEnvelopeError,
    UnsupportedSchemaError,
    UnsupportedSchemaVersionError,
)
from src.domain.services.message_deduplicator import MessageDeduplicator
from tests.fixtures.spec_examples import (
    qualified_event,
    replay_session_started,
    replay_state,
    zone_occupancy,
    zone_transition_exit,
)


def _use_case() -> IngestEnvelopeUseCase:
    return IngestEnvelopeUseCase(MessageDeduplicator())


def test_deve_converter_zone_transition_do_exemplo_da_especificacao():
    ingested = _use_case().execute(zone_transition_exit())
    message = ingested.message

    assert isinstance(message, ZoneTransition)
    assert ingested.envelope.artifact_version == "zones-a8-2"
    assert message.zone_id == "vaga-12"
    assert message.transition == "EXIT"
    assert message.object_class == "vehicle"
    assert message.dwell_s == 8395
    assert message.occurred_at == datetime(2026, 9, 23, 14, 29, 59, 200000)
    assert message.entered_at == datetime(2026, 9, 23, 12, 10, 4, 200000)


def test_deve_converter_zone_occupancy_do_exemplo_da_especificacao():
    message = _use_case().execute(zone_occupancy()).message

    assert isinstance(message, ZoneOccupancySample)
    assert message.zone_id == "vaga-12"
    assert message.count == 0
    assert message.count_by_class == {"vehicle": 0, "person": 0}
    assert message.max_occupancy == 1


def test_deve_descartar_mensagem_com_message_id_ja_processado():
    use_case = _use_case()
    use_case.execute(zone_occupancy())

    assert use_case.execute(zone_occupancy()) is None


def test_deve_aceitar_mensagem_corrigida_depois_de_uma_rejeitada_com_mesmo_message_id():
    use_case = _use_case()
    broken = zone_occupancy()
    del broken["payload"]["count"]
    with pytest.raises(MalformedEventEnvelopeError):
        use_case.execute(broken)

    assert use_case.execute(zone_occupancy()) is not None


def test_deve_aceitar_minor_mais_novo_do_mesmo_major():
    message = zone_occupancy()
    message["schema_version"] = "1.3"
    assert _use_case().execute(message) is not None


def test_deve_rejeitar_major_desconhecido():
    message = zone_occupancy()
    message["schema_version"] = "2.0"
    with pytest.raises(UnsupportedSchemaVersionError):
        _use_case().execute(message)


def test_deve_rejeitar_schema_que_o_s5_nao_consome():
    message = zone_occupancy()
    message["schema"] = "ods.i2.tracks"
    with pytest.raises(UnsupportedSchemaError):
        _use_case().execute(message)


def test_deve_rejeitar_exit_sem_dwell_s():
    message = zone_transition_exit()
    del message["payload"]["dwell_s"]
    with pytest.raises(MalformedEventEnvelopeError):
        _use_case().execute(message)


def test_deve_rejeitar_payload_sem_campo_obrigatorio():
    message = zone_transition_exit()
    del message["payload"]["zone_id"]
    with pytest.raises(MalformedEventEnvelopeError):
        _use_case().execute(message)


def test_deve_converter_s2_event_do_exemplo_da_especificacao():
    message = _use_case().execute(qualified_event()).message

    assert isinstance(message, QualifiedEvent)
    assert message.event_type == "PPE_NON_COMPLIANT"
    assert message.status == "CONFIRMED"
    assert message.phase == "STARTED"
    assert message.zone_id == "galpao-solda"
    assert message.object_class == "person"
    assert message.started_at == datetime(2026, 9, 23, 14, 29, 52)
    assert message.duration_ms == 8000


def test_deve_aceitar_s2_event_sem_source_id_e_artifact_version():
    message = qualified_event()
    del message["source_id"]
    del message["artifact_version"]
    assert _use_case().execute(message) is not None


def test_deve_rejeitar_s2_event_sem_sequence():
    message = qualified_event()
    del message["sequence"]
    with pytest.raises(MalformedEventEnvelopeError):
        _use_case().execute(message)


def test_deve_converter_session_started_do_exemplo_da_especificacao():
    message = _use_case().execute(replay_session_started()).message

    assert isinstance(message, SessionStart)
    assert message.mode == "REPLAY"
    assert message.reason == "SEEK"
    assert message.sources == ("cam0", "mic0")
    assert message.started_at == datetime(2026, 9, 23, 14, 29, 58)
    assert message.previous_session_id == "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"


def test_deve_converter_replay_state_do_exemplo_da_especificacao():
    message = _use_case().execute(replay_state()).message

    assert isinstance(message, ReplayState)
    assert message.state == "PLAYING"
    assert message.position_ms == 126000
    assert message.captured_at == datetime(2026, 9, 23, 14, 29, 59)


def test_deve_rejeitar_session_started_com_modo_desconhecido():
    message = replay_session_started()
    message["payload"]["mode"] = "SIMULATION"
    with pytest.raises(MalformedEventEnvelopeError):
        _use_case().execute(message)


def test_deve_rejeitar_session_started_com_sources_que_nao_seja_lista():
    message = replay_session_started()
    message["payload"]["sources"] = "cam0"
    with pytest.raises(MalformedEventEnvelopeError):
        _use_case().execute(message)
