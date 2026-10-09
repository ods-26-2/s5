import math
from dataclasses import FrozenInstanceError

import pytest

from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.exceptions import InvalidSpatialCellError


def test_deve_criar_celula_quando_densidade_for_valida():
    cell = SpatialCell(position=WorldCoordinate(x=1.0, y=2.0), density=0.75)
    assert cell.position.x == 1.0
    assert cell.density == 0.75


def test_deve_lancar_excecao_quando_densidade_for_negativa():
    with pytest.raises(InvalidSpatialCellError):
        SpatialCell(position=WorldCoordinate(x=0.0, y=0.0), density=-0.1)


def test_deve_lancar_excecao_quando_densidade_for_nao_finita():
    with pytest.raises(InvalidSpatialCellError):
        SpatialCell(position=WorldCoordinate(x=0.0, y=0.0), density=math.nan)


def test_deve_ser_imutavel_quando_tentar_alterar_densidade():
    cell = SpatialCell(position=WorldCoordinate(x=0.0, y=0.0), density=1.0)
    with pytest.raises(FrozenInstanceError):
        cell.density = 9.9