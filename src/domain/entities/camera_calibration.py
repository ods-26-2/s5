from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import InvalidArtifactError


@dataclass(frozen=True)
class CameraCalibration:
    """Calibração de uma câmera publicada por I3 (artefato CALIBRATION, seção 8).

    O S5 guarda só o que usa: a qual plano (space_id) a câmera pertence, desde quando e
    em que versão. A conversão de pixels para metros já é feita pelo S1, que entrega
    position_m em ods.s1.position.
    """

    source_id: str
    artifact_version: str
    space_id: str
    valid_from: datetime
    reprojection_rms_cm: float | None = None

    def __post_init__(self) -> None:
        for name in ("source_id", "artifact_version", "space_id"):
            if not getattr(self, name).strip():
                raise InvalidArtifactError(f"{name} não pode ser vazio na calibração.")
