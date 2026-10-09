import pytest

from src.domain.services.grid_density_calculator import GridDensityCalculator
from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.domain.exceptions import InvalidHeatmapGridError


def test_deve_retornar_grade_vazia_quando_nao_houver_pontos():
    grid = GridDensityCalculator(cell_size=1.0).calculate(points=[], grid_id="grid-01")
    assert grid.cells == ()


def test_deve_agrupar_pontos_na_mesma_celula_e_normalizar_densidade():
    points = [
        WorldCoordinate(x=0.1, y=0.1),
        WorldCoordinate(x=0.2, y=0.2),
        WorldCoordinate(x=5.0, y=5.0),
    ]
    grid = GridDensityCalculator(cell_size=1.0).calculate(points=points, grid_id="grid-01")

    densities = {round(cell.density, 2) for cell in grid.cells}
    assert len(grid.cells) == 2
    assert 1.0 in densities
    assert 0.5 in densities


def test_deve_lancar_excecao_quando_cell_size_nao_for_positivo():
    with pytest.raises(InvalidHeatmapGridError):
        GridDensityCalculator(cell_size=0)
