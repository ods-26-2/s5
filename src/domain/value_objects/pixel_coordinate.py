import math
from dataclasses import dataclass

from src.domain.exceptions import InvalidPixelCoordinateError


@dataclass(frozen=True)
class PixelCoordinate:
    """Ponto em coordenadas de pixel (u, v) de uma imagem de câmera."""

    u: float
    v: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.u) or not math.isfinite(self.v):
            raise InvalidPixelCoordinateError(
                f"Coordenada de pixel exige valores finitos, recebido (u={self.u}, v={self.v})."
            )
