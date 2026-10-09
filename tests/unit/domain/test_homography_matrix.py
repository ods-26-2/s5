import math

import pytest

from src.domain.value_objects.homography_matrix import HomographyMatrix
from src.domain.value_objects.pixel_coordinate import PixelCoordinate
from src.domain.exceptions import InvalidHomographyMatrixError

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_deve_projetar_pixel_quando_matriz_for_identidade():
    homography = HomographyMatrix(matrix=IDENTITY)
    world = homography.project(PixelCoordinate(u=3.0, v=4.0))
    assert world.x == 3.0
    assert world.y == 4.0


def test_deve_escalar_coordenadas_quando_matriz_aplicar_fator():
    scale_by_two = ((2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 1.0))
    homography = HomographyMatrix(matrix=scale_by_two)
    world = homography.project(PixelCoordinate(u=3.0, v=4.0))
    assert world.x == 6.0
    assert world.y == 8.0


def test_deve_lancar_excecao_quando_matriz_nao_for_3x3():
    with pytest.raises(InvalidHomographyMatrixError):
        HomographyMatrix(matrix=((1.0, 0.0), (0.0, 1.0)))


def test_deve_lancar_excecao_quando_matriz_contiver_valor_nao_finito():
    invalid = ((math.nan, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    with pytest.raises(InvalidHomographyMatrixError):
        HomographyMatrix(matrix=invalid)
