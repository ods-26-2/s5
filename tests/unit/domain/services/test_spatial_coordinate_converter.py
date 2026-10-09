from src.domain.services.spatial_coordinate_converter import SpatialCoordinateConverter
from src.domain.value_objects.homography_matrix import HomographyMatrix
from src.domain.value_objects.pixel_coordinate import PixelCoordinate

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_deve_converter_pixel_em_coordenada_de_mundo_quando_homografia_for_identidade():
    homography = HomographyMatrix(matrix=IDENTITY)
    world = SpatialCoordinateConverter().convert(PixelCoordinate(u=5.0, v=7.0), homography)
    assert world.x == 5.0
    assert world.y == 7.0
