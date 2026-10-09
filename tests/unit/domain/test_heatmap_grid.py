import pytest

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.domain.exceptions import InvalidHeatmapGridError


def test_deve_criar_grade_quando_grid_id_for_valido():
    cell = SpatialCell(position=WorldCoordinate(x=0.0, y=0.0), density=0.5)
    grid = HeatmapGrid(grid_id="grid-01", cells=(cell,))
    assert grid.grid_id == "grid-01"
    assert grid.cells == (cell,)


def test_deve_criar_grade_vazia_quando_nao_houver_celulas():
    grid = HeatmapGrid(grid_id="grid-01", cells=())
    assert grid.cells == ()


def test_deve_lancar_excecao_quando_grid_id_for_vazio():
    with pytest.raises(InvalidHeatmapGridError):
        HeatmapGrid(grid_id="", cells=())
