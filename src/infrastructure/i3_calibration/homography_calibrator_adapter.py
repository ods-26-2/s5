import json
from pathlib import Path

from src.domain.value_objects.homography_matrix import HomographyMatrix


class HomographyCalibratorAdapter:
    """Carrega a matriz de homografia I3 (3x3) de um arquivo de calibração JSON em disco."""

    def load(self, calibration_path: Path | str) -> HomographyMatrix:
        with open(calibration_path, encoding="utf-8") as file:
            payload = json.load(file)
        matrix = tuple(tuple(row) for row in payload["homography_matrix"])
        return HomographyMatrix(matrix=matrix)
