import threading
from dataclasses import dataclass

from src.domain.entities.camera_calibration import CameraCalibration
from src.domain.entities.zones_artifact import METERS, ZoneDefinition, ZonesArtifact


@dataclass(frozen=True)
class ZoneEntry:
    """Uma zona e o artefato ZONES que a define."""

    zone: ZoneDefinition
    artifact: ZonesArtifact

    @property
    def space_id(self) -> str | None:
        return self.artifact.space_id if self.artifact.coordinates == METERS else None


class ArtifactCatalog:
    """Versão vigente de cada artefato que o S5 usa: os conjuntos de zonas, por artifact_id,
    e a calibração de cada câmera. Uma versão nova substitui a anterior do mesmo artefato
    (Especificação 1.0, seção 8: uma versão nunca muda; correção é versão nova).

    É lido pela leitura do barramento, pelo fechamento de janelas e pela API, em threads
    diferentes; as trocas acontecem sob um lock e as leituras recebem cópias.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._zones: dict[str, ZonesArtifact] = {}
        self._calibrations: dict[str, CameraCalibration] = {}

    def put_zones(self, artifact: ZonesArtifact) -> None:
        with self._lock:
            self._zones[artifact.artifact_id] = artifact

    def put_calibration(self, calibration: CameraCalibration) -> None:
        with self._lock:
            self._calibrations[calibration.source_id] = calibration

    def zone_entries(self) -> dict[str, ZoneEntry]:
        """Toda zona definida pelos artefatos vigentes. Se dois artefatos definirem a mesma
        zone_id, vale o de artifact_id maior em ordem alfabética, de forma previsível."""
        with self._lock:
            artifacts = sorted(self._zones.values(), key=lambda a: a.artifact_id)
        return {zone.zone_id: ZoneEntry(zone, artifact) for artifact in artifacts for zone in artifact.zones}

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_entries()

    def calibration(self, source_id: str) -> CameraCalibration | None:
        with self._lock:
            return self._calibrations.get(source_id)

    def versions(self) -> dict[str, str]:
        """artifact_id → versão vigente, para registro e diagnóstico."""
        with self._lock:
            loaded = {a.artifact_id: a.artifact_version for a in self._zones.values()}
            loaded.update({f"cal-{c.source_id}": c.artifact_version for c in self._calibrations.values()})
        return loaded
