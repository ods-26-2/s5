import hashlib
import json
import logging

from src.application.parsers.artifact_parser import (
    ArtifactDescriptor,
    calibration_source_id,
    parse_calibration,
    parse_zones,
)
from src.application.ports.artifact_source import IArtifactSource
from src.application.state.artifact_catalog import ArtifactCatalog
from src.domain.exceptions import ArtifactUnavailableError, InvalidArtifactError

ZONES = "ZONES"
CALIBRATION = "CALIBRATION"
SUPPORTED_KINDS = (ZONES, CALIBRATION)

logger = logging.getLogger(__name__)


class LoadArtifactUseCase:
    """Carrega um artefato pelo descritor comum: busca o conteúdo pela URI, confere o
    hash_sha256 e, se for de um tipo que o S5 usa, o põe no catálogo.

    Artefatos de outros tipos (RULES, ROUTING, MODEL…) são ignorados e devolvem False: o
    anúncio ods.artifact.published é um tópico só para todos os tipos.
    """

    def __init__(self, source: IArtifactSource, catalog: ArtifactCatalog) -> None:
        self._source = source
        self._catalog = catalog

    def execute(self, descriptor: ArtifactDescriptor) -> bool:
        if descriptor.kind not in SUPPORTED_KINDS:
            return False
        content = self._fetch_verified(descriptor)
        if descriptor.kind == ZONES:
            self._catalog.put_zones(
                parse_zones(content, descriptor.artifact_id, descriptor.artifact_version, descriptor.owner)
            )
        else:
            self._catalog.put_calibration(
                parse_calibration(content, calibration_source_id(descriptor.artifact_id), descriptor.artifact_version)
            )
        logger.info("Artefato carregado: %s %s", descriptor.kind, descriptor.artifact_version)
        return True

    def _fetch_verified(self, descriptor: ArtifactDescriptor) -> dict:
        raw = self._source.fetch(descriptor.uri)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != descriptor.hash_sha256:
            raise ArtifactUnavailableError(
                f"{descriptor.artifact_version}: hash_sha256 não confere com o conteúdo de {descriptor.uri}."
            )
        try:
            content = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidArtifactError(f"{descriptor.artifact_version}: conteúdo não é JSON ({error}).") from error
        if not isinstance(content, dict):
            raise InvalidArtifactError(f"{descriptor.artifact_version}: conteúdo deve ser um objeto JSON.")
        return content
