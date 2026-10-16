import pytest

from src.domain.services.message_deduplicator import MessageDeduplicator


def test_deve_reconhecer_message_id_registrado():
    deduplicator = MessageDeduplicator()
    deduplicator.register("m-1")
    assert deduplicator.is_duplicate("m-1") is True
    assert deduplicator.is_duplicate("m-2") is False


def test_deve_esquecer_o_id_mais_antigo_ao_exceder_a_capacidade():
    deduplicator = MessageDeduplicator(capacity=2)
    for message_id in ("m-1", "m-2", "m-3"):
        deduplicator.register(message_id)

    assert deduplicator.is_duplicate("m-1") is False
    assert deduplicator.is_duplicate("m-3") is True


def test_deve_rejeitar_capacidade_nao_positiva():
    with pytest.raises(ValueError):
        MessageDeduplicator(capacity=0)
