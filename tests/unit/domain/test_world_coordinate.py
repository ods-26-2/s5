import math
from dataclasses import FrozenInstanceError

import pytest

from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.domain.exceptions import InvalidWorldCoordinateError


def test_deve_criar_coordenada_quando_valores_forem_finitos():
    coord = WorldCoordinate(x=3.5, y=-2.0)
    assert coord.x == 3.5
    assert coord.y == -2.0


def test_deve_lancar_excecao_quando_x_for_nao_finito():
    with pytest.raises(InvalidWorldCoordinateError):
        WorldCoordinate(x=math.inf, y=0.0)


def test_deve_ser_imutavel_quando_tentar_alterar_atributo():
    coord = WorldCoordinate(x=1.0, y=1.0)
    with pytest.raises(FrozenInstanceError):
        coord.x = 9.9