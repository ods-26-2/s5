from src.domain.value_objects.homography_matrix import HomographyMatrix
from src.domain.value_objects.pixel_coordinate import PixelCoordinate
from src.domain.value_objects.world_coordinate import WorldCoordinate


class SpatialCoordinateConverter:
    """Converte coordenadas de pixel em coordenadas métricas de mundo via homografia I3."""

    def convert(self, pixel: PixelCoordinate, homography: HomographyMatrix) -> WorldCoordinate:
        return homography.project(pixel)
