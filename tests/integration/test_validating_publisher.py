import json

from src.infrastructure.contracts.contract_validator import CONTRACTS_DIR, ContractValidator, ValidatingPublisher
from tests.unit.application.test_close_metric_windows_use_case import RecordingPublisher

VALID = json.loads((CONTRACTS_DIR / "examples/ods.s5.zone_metrics/valid-vaga-12-15m.json").read_text())
INVALID = json.loads(
    (CONTRACTS_DIR / "examples/ods.s5.zone_metrics/invalid-nome-antigo-dwell_time_avg.json").read_text()
)


def _publisher():
    inner = RecordingPublisher()
    violations = []
    publisher = ValidatingPublisher(inner, ContractValidator(), lambda message, error: violations.append(error))
    return publisher, inner, violations


def test_mensagem_dentro_do_contrato_chega_ao_barramento():
    publisher, inner, violations = _publisher()
    publisher.publish("ods.s5.zone_metrics", VALID)
    assert inner.published == [("ods.s5.zone_metrics", VALID)] and violations == []


def test_mensagem_fora_do_contrato_e_descartada_e_relatada():
    publisher, inner, violations = _publisher()
    publisher.publish("ods.s5.zone_metrics", INVALID)

    assert inner.published == []
    [error] = violations
    assert error.schema == "ods.s5.zone_metrics"
    assert any("dwell_avg_s" in problem for problem in error.problems)


def test_mensagem_em_topico_diferente_do_schema_e_descartada():
    publisher, inner, violations = _publisher()
    publisher.publish("ods.s5.event_metrics", VALID)
    assert inner.published == [] and len(violations) == 1


def test_schema_sem_contrato_e_descartado():
    publisher, inner, violations = _publisher()
    publisher.publish("ods.s5.outra", {**VALID, "schema": "ods.s5.outra"})
    assert inner.published == [] and "não há contrato" in violations[0].problems[0]
