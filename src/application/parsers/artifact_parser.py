from dataclasses import dataclass
from datetime import datetime

from src.application.parsers.envelope_parser import parse_utc_timestamp
from src.domain.entities.camera_calibration import CameraCalibration
from src.domain.entities.zones_artifact import ZoneDefinition, ZonesArtifact
from src.domain.exceptions import InvalidArtifactError, MalformedEventEnvelopeError

DESCRIPTOR_FIELDS = (
    "artifact_id", "artifact_version", "kind", "owner", "uri", "hash_sha256", "valid_from", "schema_version"
)


@dataclass(frozen=True)
class ArtifactDescriptor:
    """Descritor comum de artefato (Especificação 1.0, seção 8); também é o payload de
    ods.artifact.published."""

    artifact_id: str
    artifact_version: str
    kind: str
    owner: str
    uri: str
    hash_sha256: str
    valid_from: datetime
    schema_version: str


def parse_descriptor(raw: dict) -> ArtifactDescriptor:
    if not isinstance(raw, dict):
        raise InvalidArtifactError("O descritor de artefato deve ser um objeto.")
    missing = [name for name in DESCRIPTOR_FIELDS if raw.get(name) in (None, "")]
    if missing:
        raise InvalidArtifactError(f"Campos ausentes no descritor de artefato: {missing}.")
    return ArtifactDescriptor(
        artifact_id=raw["artifact_id"],
        artifact_version=raw["artifact_version"],
        kind=raw["kind"],
        owner=raw["owner"],
        uri=raw["uri"],
        hash_sha256=str(raw["hash_sha256"]).lower(),
        valid_from=_timestamp(raw["valid_from"], "valid_from"),
        schema_version=raw["schema_version"],
    )


def parse_zones(content: dict, artifact_id: str, artifact_version: str, owner: str | None = None) -> ZonesArtifact:
    """Conteúdo do artefato ZONES → ZonesArtifact."""
    try:
        return ZonesArtifact(
            artifact_id=artifact_id,
            artifact_version=artifact_version,
            coordinates=content["coordinates"],
            source_ids=tuple(content["source_ids"]),
            space_id=content.get("space_id"),
            owner=owner,
            zones=tuple(
                ZoneDefinition(
                    zone_id=zone["zone_id"],
                    name=zone["name"],
                    polygon=tuple(tuple(float(v) for v in point) for point in zone["polygon"]),
                    enter_hysteresis_ms=zone["enter_hysteresis_ms"],
                    exit_hysteresis_ms=zone["exit_hysteresis_ms"],
                    max_occupancy=zone.get("max_occupancy"),
                    classes=tuple(zone["classes"]) if zone.get("classes") is not None else None,
                )
                for zone in content["zones"]
            ),
        )
    except KeyError as error:
        raise InvalidArtifactError(f"Campo obrigatório ausente no artefato ZONES: {error}") from error
    except (TypeError, ValueError, AttributeError) as error:
        raise InvalidArtifactError(f"Artefato ZONES inválido: {error}") from error


def parse_calibration(content: dict, source_id: str, artifact_version: str) -> CameraCalibration:
    """Conteúdo do artefato CALIBRATION (o payload de ods.i3.calibration) → CameraCalibration.
    A homografia é exigida, embora o S5 não a aplique, para recusar calibração incompleta."""
    try:
        homography = content["homography_px_to_m"]
        if len(homography) != 3 or any(len(row) != 3 for row in homography):
            raise InvalidArtifactError("homography_px_to_m deve ser uma matriz 3×3.")
        return CameraCalibration(
            source_id=source_id,
            artifact_version=artifact_version,
            space_id=content["reference_frame"]["space_id"],
            valid_from=_timestamp(content["valid_from"], "valid_from"),
            reprojection_rms_cm=content.get("reprojection_rms_cm"),
        )
    except KeyError as error:
        raise InvalidArtifactError(f"Campo obrigatório ausente na calibração: {error}") from error
    except (TypeError, AttributeError) as error:
        raise InvalidArtifactError(f"Calibração inválida: {error}") from error


def calibration_source_id(artifact_id: str) -> str:
    """O artefato de calibração de uma câmera se chama cal-<source_id> (seção 6, I3)."""
    if not artifact_id.startswith("cal-") or len(artifact_id) <= 4:
        raise InvalidArtifactError(f"artifact_id de calibração fora do padrão cal-<source_id>: {artifact_id!r}.")
    return artifact_id.removeprefix("cal-")


def _timestamp(value: object, field_name: str) -> datetime:
    try:
        return parse_utc_timestamp(value, field_name)
    except MalformedEventEnvelopeError as error:
        raise InvalidArtifactError(str(error)) from error


