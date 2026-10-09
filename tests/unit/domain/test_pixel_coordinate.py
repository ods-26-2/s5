import math
from dataclasses import FrozenInstanceError

import pytest

from src.domain.value_objects.pixel_coordinate import PixelCoordinate
from src.domain.exceptions import InvalidPixelCoordinateError


def test_deve_criar_coordenada_quando_valores_forem_finitos():
    pixel = PixelCoordinate(u=10.0, v=20.0)
    assert pixel.u == 10.0
    assert pixel.v == 20.0


def test_deve_lancar_excecao_quando_v_for_nao_finito():
    with pytest.raises(InvalidPixelCoordinateError):
        PixelCoordinate(u=0.0, v=math.nan)


def test_deve_ser_imutavel_quando_tentar_alterar_atributo():
    pixel = PixelCoordinate(u=1.0, v=1.0)
    with pytest.raises(FrozenInstanceError):
        pixel.u = 9.9
