from datetime import datetime

import pytest

from src.application.parsers.envelope_parser import (
    EV_SINAL_FIELDS,
    parse_envelope,
    parse_utc_timestamp,
)
from src.domain.exceptions import MalformedEventEnvelopeError
from tests.fixtures.spec_examples import zone_occupancy


def test_deve_ler_os_campos_do_envelope_quando_mensagem_for_valida():
    envelope = parse_envelope(zone_occupancy(), required_fields=EV_SINAL_FIELDS)

    assert envelope.schema == "ods.s1.zone_occupancy"
    assert envelope.producer == "S1"
    assert envelope.source_id == "cam0"
    assert envelope.sequence == 1205
    assert envelope.artifact_version == "zones-a8-2"
    assert envelope.captured_at == datetime(2026, 9, 23, 14, 29, 59, 200000)


def test_deve_converter_marco_com_fuso_para_utc_sem_tzinfo():
    parsed = parse_utc_timestamp("2026-09-23T11:29:59.870-03:00", "captured_at")
    assert parsed == datetime(2026, 9, 23, 14, 29, 59, 870000)
    assert parsed.tzinfo is None


def test_deve_rejeitar_marco_sem_fuso():
    with pytest.raises(MalformedEventEnvelopeError):
        parse_utc_timestamp("2026-09-23T14:29:59.870", "captured_at")


@pytest.mark.parametrize("field", ["message_id", "schema_version", "published_at", "payload"])
def test_deve_rejeitar_mensagem_sem_campo_fixo(field):
    message = zone_occupancy()
    del message[field]
    with pytest.raises(MalformedEventEnvelopeError):
        parse_envelope(message)


@pytest.mark.parametrize("field", EV_SINAL_FIELDS)
def test_deve_rejeitar_mensagem_sem_campo_do_perfil_ev_sinal(field):
    message = zone_occupancy()
    del message[field]
    with pytest.raises(MalformedEventEnvelopeError):
        parse_envelope(message, required_fields=EV_SINAL_FIELDS)


def test_deve_rejeitar_message_type_fora_do_enum():
    message = zone_occupancy()
    message["message_type"] = "evento"
    with pytest.raises(MalformedEventEnvelopeError):
        parse_envelope(message)


def test_deve_rejeitar_sequence_que_nao_seja_inteiro():
    message = zone_occupancy()
    message["sequence"] = "1205"
    with pytest.raises(MalformedEventEnvelopeError):
        parse_envelope(message)
