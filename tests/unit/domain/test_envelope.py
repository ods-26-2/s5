from datetime import datetime

import pytest

from src.domain.exceptions import InvalidEnvelopeError
from src.domain.value_objects.envelope import Envelope


def _envelope(**overrides) -> Envelope:
    fields = dict(
        message_type="event",
        message_id="m-1",
        schema="ods.s1.zone_occupancy",
        schema_version="1.0",
        producer="S1",
        published_at=datetime(2026, 9, 23, 14, 30),
        payload={},
    )
    fields.update(overrides)
    return Envelope(**fields)


def test_deve_expor_o_major_do_schema_version():
    assert _envelope(schema_version="1.4").schema_major == 1


@pytest.mark.parametrize("schema_version", ["1", "1.0.0", "v1.0", ""])
def test_deve_rejeitar_schema_version_fora_de_major_minor(schema_version):
    with pytest.raises(InvalidEnvelopeError):
        _envelope(schema_version=schema_version)


def test_deve_rejeitar_message_type_desconhecido():
    with pytest.raises(InvalidEnvelopeError):
        _envelope(message_type="notification")


def test_deve_rejeitar_message_id_vazio():
    with pytest.raises(InvalidEnvelopeError):
        _envelope(message_id="  ")


def test_deve_rejeitar_sequence_negativo():
    with pytest.raises(InvalidEnvelopeError):
        _envelope(sequence=-1)
