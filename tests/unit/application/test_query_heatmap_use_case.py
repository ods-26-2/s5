from datetime import datetime

import pytest

from src.application.use_cases.query_heatmap_use_case import QueryHeatmapUseCase
from src.domain.exceptions import QueryRejectedError
from src.domain.services.presence_accumulator import PresenceKey
from tests.fixtures.spec_examples import heatmap_query

from .fakes import FakeTimeSeriesRepository

BUCKET = datetime(2026, 9, 23, 14, 10)


def _repository(*cells, kind="METERS", key="patio-1", object_class="person", mode="LIVE"):
    repository = FakeTimeSeriesRepository()
    repository.save_presence(
        [(PresenceKey("s-1", kind, key, object_class, x, y, BUCKET), seconds, mode) for x, y, seconds in cells]
    )
    return repository


def test_deve_agrupar_celulas_finas_no_tamanho_pedido():
    # 0,1 m → 0,5 m: células finas 0–4 vão para a 0, 5–9 para a 1.
    repository = _repository((4, 0, 3.0), (5, 0, 7.4), (9, 4, 2.0), (34, 71, 12.0))

    reply = QueryHeatmapUseCase(repository).execute(heatmap_query()["payload"])

    assert reply["grid_width"] == 7 and reply["grid_height"] == 15
    assert reply["origin"] == [0.0, 0.0]
    assert reply["cell_size_m"] == 0.5
    assert reply["cells"][0][:2] == [3, 9]
    assert reply["cells"][14][6] == 12


def test_origem_e_o_canto_da_primeira_celula_com_presenca():
    reply = QueryHeatmapUseCase(_repository((34, 71, 12.0))).execute(heatmap_query()["payload"])

    assert reply["origin"] == [3.0, 7.0]
    assert reply["cells"] == [[12]]


def test_deve_atender_em_pixels_por_camera():
    payload = heatmap_query()["payload"]
    del payload["space_id"], payload["cell_size_m"]
    payload.update(source_id="cam0", cell_size_px=20)

    reply = QueryHeatmapUseCase(_repository((50, 70, 4.0), kind="PIXELS", key="cam0")).execute(payload)

    assert reply["cell_size_px"] == 20 and reply["origin"] == [500, 700] and reply["cells"] == [[4]]


def test_deve_devolver_grade_vazia_sem_presenca():
    reply = QueryHeatmapUseCase(FakeTimeSeriesRepository()).execute(heatmap_query()["payload"])
    assert reply["grid_width"] == 0 and reply["cells"] == []


def test_deve_filtrar_por_classe():
    reply = QueryHeatmapUseCase(_repository((1, 1, 5.0), object_class="vehicle")).execute(heatmap_query()["payload"])
    assert reply["cells"] == []


def test_deve_recusar_grade_acima_de_200_por_200():
    repository = _repository((0, 0, 1.0), (1000, 0, 1.0))
    with pytest.raises(QueryRejectedError) as error:
        QueryHeatmapUseCase(repository).execute(heatmap_query()["payload"])
    assert error.value.code == "GRID_TOO_LARGE"


@pytest.mark.parametrize("change", [{"cell_size_m": 0.05}, {"cell_size_m": "0.5"}, {"space_id": None}])
def test_deve_recusar_consulta_invalida(change):
    payload = heatmap_query()["payload"]
    payload.update(change)
    with pytest.raises(QueryRejectedError) as error:
        QueryHeatmapUseCase(FakeTimeSeriesRepository()).execute(payload)
    assert error.value.code == "INVALID_QUERY"
