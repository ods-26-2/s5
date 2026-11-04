from datetime import datetime

import pytest

from src.domain.entities.camera_calibration import CameraCalibration
from src.domain.entities.zones_artifact import ZoneDefinition, ZonesArtifact
from src.domain.exceptions import InvalidArtifactError

SQUARE = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))


def _zone(**overrides) -> ZoneDefinition:
    fields = dict(zone_id="z-1", name="Z 1", polygon=SQUARE, enter_hysteresis_ms=500, exit_hysteresis_ms=1500)
    fields.update(overrides)
    return ZoneDefinition(**fields)


def _artifact(**overrides) -> ZonesArtifact:
    fields = dict(
        artifact_id="zones-a8", artifact_version="zones-a8-2", coordinates="METERS",
        source_ids=("cam0",), zones=(_zone(),), space_id="patio-1",
    )
    fields.update(overrides)
    return ZonesArtifact(**fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"polygon": SQUARE[:2]},
        {"polygon": ((0.0, 0.0), (1.0, float("nan")), (1.0, 1.0))},
        {"exit_hysteresis_ms": -1},
        {"max_occupancy": -1},
        {"zone_id": " "},
    ],
)
def test_deve_rejeitar_zona_invalida(overrides):
    with pytest.raises(InvalidArtifactError):
        _zone(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"space_id": None},
        {"coordinates": "PIXELS", "space_id": None, "source_ids": ("cam0", "cam1")},
        {"coordinates": "FEET"},
        {"source_ids": ()},
        {"zones": (_zone(), _zone())},
    ],
)
def test_deve_rejeitar_artefato_de_zonas_invalido(overrides):
    with pytest.raises(InvalidArtifactError):
        _artifact(**overrides)


def test_zonas_em_pixels_de_uma_camera_nao_precisam_de_space_id():
    artifact = _artifact(coordinates="PIXELS", space_id=None)
    assert artifact.single_source_id == "cam0"


def test_calibracao_exige_space_id():
    with pytest.raises(InvalidArtifactError):
        CameraCalibration(source_id="cam0", artifact_version="cal-cam0-3", space_id="", valid_from=datetime(2026, 9, 20))
