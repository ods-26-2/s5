import json

from src.infrastructure.i3_calibration.homography_calibrator_adapter import (
    HomographyCalibratorAdapter,
)
from src.domain.value_objects.pixel_coordinate import PixelCoordinate


def test_deve_carregar_matriz_de_homografia_de_arquivo_json(tmp_path):
    calibration_file = tmp_path / "camera-01.json"
    calibration_file.write_text(
        json.dumps({"homography_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]})
    )

    homography = HomographyCalibratorAdapter().load(calibration_file)
    world = homography.project(PixelCoordinate(u=2.0, v=3.0))

    assert world.x == 2.0
    assert world.y == 3.0
