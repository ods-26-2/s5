from datetime import datetime

from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase
from src.domain.services.message_deduplicator import MessageDeduplicator
from tests.fixtures.spec_examples import qualified_event, zone_occupancy, zone_transition_exit


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


def test_deve_descartar_antigos_mas_manter_ultima_amostra_e_evento_aberto():
    buffer = _buffer()
    buffer.prune(before=datetime(2026, 9, 24))

    assert buffer.transitions == []
    assert [s.zone_id for s in buffer.samples] == ["vaga-12"]
    assert len(buffer.events) == 1
