"""Os exemplos de contracts/examples são a primeira entrada da suíte de contrato de B4:
cada arquivo valid-* precisa passar no schema e cada invalid-* precisa ser recusado."""

import json
from pathlib import Path

import pytest

from src.application.use_cases.query_heatmap_use_case import QueryHeatmapUseCase
from src.application.use_cases.query_metrics_use_case import INVALID_QUERY, QueryMetricsUseCase
from src.domain.exceptions import QueryRejectedError
from src.infrastructure.contracts.contract_validator import CONTRACTS_DIR, ContractValidator
from tests.unit.application.fakes import FakeTimeSeriesRepository

EXAMPLES = sorted((CONTRACTS_DIR / "examples").rglob("*.json"))
VALIDATOR = ContractValidator()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _id(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"


def test_cada_contrato_do_s5_tem_exemplo_valido_e_invalido():
    for schema in VALIDATOR.schemas:
        names = [p.name for p in EXAMPLES if p.parent.name == schema]
        assert any(n.startswith("valid-") for n in names), schema
        assert any(n.startswith("invalid-") for n in names), schema


def test_exemplos_ficam_na_pasta_do_proprio_schema():
    for path in EXAMPLES:
        assert _load(path)["schema"] == path.parent.name, path


@pytest.mark.parametrize("path", [p for p in EXAMPLES if p.name.startswith("valid-")], ids=_id)
def test_exemplo_valido_passa_no_schema(path):
    assert VALIDATOR.problems(_load(path)) == []


@pytest.mark.parametrize("path", [p for p in EXAMPLES if p.name.startswith("invalid-")], ids=_id)
def test_exemplo_invalido_e_recusado_pelo_schema(path):
    assert VALIDATOR.problems(_load(path)) != []


@pytest.mark.parametrize(
    "path",
    [p for p in EXAMPLES if p.name.startswith("valid-") and p.parent.name.endswith(".query")],
    ids=_id,
)
def test_consulta_valida_pelo_schema_nao_e_recusada_como_invalida_pelo_s5(path):
    """O schema e o caso de uso precisam concordar sobre o que é uma consulta bem formada."""
    use_cases = {
        "ods.s5.metrics.query": QueryMetricsUseCase(FakeTimeSeriesRepository()),
        "ods.s5.heatmap.query": QueryHeatmapUseCase(FakeTimeSeriesRepository()),
    }
    message = _load(path)
    try:
        use_cases[message["schema"]].execute(message["payload"])
    except QueryRejectedError as error:
        assert error.code != INVALID_QUERY, error.message
