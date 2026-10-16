from datetime import datetime

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory, format_utc
from src.application.parsers.envelope_parser import EV_SERVICO_FIELDS, parse_envelope


def _factory() -> OutgoingEnvelopeFactory:
    ids = iter(f"id-{n}" for n in range(100))
    return OutgoingEnvelopeFactory(clock=lambda: datetime(2026, 9, 23, 14, 15, 2, 5000), id_factory=lambda: next(ids))


def test_deve_formatar_marco_em_iso_8601_com_milissegundos_e_z():
    assert format_utc(datetime(2026, 9, 23, 14, 15)) == "2026-09-23T14:15:00.000Z"


def test_deve_montar_envelope_ev_servico_que_o_proprio_parser_aceita():
    message = _factory().service_event(
        "ods.s5.zone_metrics", {"zone_id": "vaga-12"},
        captured_at=datetime(2026, 9, 23, 14, 15), session_id="s-1", artifact_version="zones-a8-2",
    )

    envelope = parse_envelope(message, required_fields=EV_SERVICO_FIELDS)
    assert envelope.producer == "S5"
    assert envelope.schema_version == "1.0"
    assert message["published_at"] == "2026-09-23T14:15:02.005Z"
    assert message["artifact_version"] == "zones-a8-2"
    assert "source_id" not in message


def test_deve_numerar_sequence_por_sessao_a_partir_de_zero():
    factory = _factory()
    at = datetime(2026, 9, 23, 14, 15)
    sequences = [factory.service_event("x", {}, at, session)["sequence"] for session in ("s-1", "s-1", "s-2", "s-1")]
    assert sequences == [0, 1, 0, 2]
