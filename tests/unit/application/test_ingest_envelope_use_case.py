from datetime import datetime

import pytest

from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ZoneTransition
from src.domain.exceptions import (
    MalformedEventEnvelopeError,
    UnsupportedSchemaError,
    UnsupportedSchemaVersionError,
)
from src.domain.services.message_deduplicator import MessageDeduplicator
from tests.fixtures.spec_examples import zone_occupancy, zone_transition_exit


def _use_case() -> IngestEnvelopeUseCase:
    return IngestEnvelopeUseCase(MessageDeduplicator())


def test_deve_converter_zone_transition_do_exemplo_da_especificacao():
    message = _use_case().execute(zone_transition_exit())

    assert isinstance(message, ZoneTransition)
    assert message.zone_id == "vaga-12"
    assert message.transition == "EXIT"
    assert message.object_class == "vehicle"
    assert message.dwell_s == 8395
    assert message.occurred_at == datetime(2026, 9, 23, 14, 29, 59, 200000)
    assert message.entered_at == datetime(2026, 9, 23, 12, 10, 4, 200000)


def test_deve_converter_zone_occupancy_do_exemplo_da_especificacao():
    message = _use_case().execute(zone_occupancy())

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
