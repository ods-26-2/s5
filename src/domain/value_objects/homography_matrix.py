import math
from dataclasses import dataclass

from src.domain.exceptions import InvalidHomographyMatrixError
from src.domain.value_objects.pixel_coordinate import PixelCoordinate
from src.domain.value_objects.world_coordinate import WorldCoordinate


@dataclass(frozen=True)
class HomographyMatrix:
    """Matriz de homografia I3 (3x3) que projeta pixels (u, v) no plano de mundo."""

    matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

    def __post_init__(self) -> None:
        if len(self.matrix) != 3 or any(len(row) != 3 for row in self.matrix):
            raise InvalidHomographyMatrixError(
                f"Matriz de homografia deve ser 3x3, recebido formato {len(self.matrix)}."
            )
        if any(not math.isfinite(value) for row in self.matrix for value in row):
            raise InvalidHomographyMatrixError("Matriz de homografia exige apenas valores finitos.")

    def project(self, pixel: PixelCoordinate) -> WorldCoordinate:
        homogeneous_pixel = (pixel.u, pixel.v, 1.0)
        x, y, w = (
            sum(self.matrix[row][col] * homogeneous_pixel[col] for col in range(3)) for row in range(3)
        )
        if w == 0:
            raise InvalidHomographyMatrixError(
                "Projeção inválida: componente homogênea w resultou em zero."
            )
        return WorldCoordinate(x=x / w, y=y / w)
