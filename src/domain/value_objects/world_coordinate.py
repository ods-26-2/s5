import math
from dataclasses import dataclass

from src.domain.exceptions import InvalidWorldCoordinateError


@dataclass(frozen=True)
class WorldCoordinate:
    """Ponto em coordenadas métricas de mundo (X, Y), em metros.

    Saída da conversão por homografia do componente I3: recebe pixels (u, v)
    e devolve a posição real no plano do mundo.
    """

    x: float
    y: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise InvalidWorldCoordinateError(
                f"Coordenada de mundo exige valores finitos, recebido (x={self.x}, y={self.y})."
            )