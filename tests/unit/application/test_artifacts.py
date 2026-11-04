import json
from datetime import datetime
from pathlib import Path

import pytest

from src.application.parsers.artifact_parser import parse_descriptor, parse_zones
from src.application.ports.artifact_source import IArtifactSource
from src.application.state.artifact_catalog import ArtifactCatalog
from src.application.use_cases.handle_artifact_message_use_case import HandleArtifactMessageUseCase
from src.application.use_cases.load_artifact_use_case import LoadArtifactUseCase
from src.domain.exceptions import ArtifactUnavailableError, InvalidArtifactError, MalformedEventEnvelopeError
from src.domain.services.message_deduplicator import MessageDeduplicator

ARTIFACTS = Path(__file__).resolve().parents[2] / "fixtures" / "artifacts"


class DictSource(IArtifactSource):
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def fetch(self, uri: str) -> bytes:
        if uri not in self.files:
            raise ArtifactUnavailableError(uri)
        return self.files[uri]


def _descriptor(name: str) -> dict:
    return json.loads((ARTIFACTS / f"{name}.descriptor.json").read_text())


def _loader(**extra):
    files = {f"{n}.json": (ARTIFACTS / f"{n}.json").read_bytes() for n in ("zones-a8-2", "cal-cam0-3")}
    files.update(extra)
    catalog = ArtifactCatalog()
    return LoadArtifactUseCase(DictSource(files), catalog), catalog


def test_deve_carregar_zonas_conferindo_o_hash():
    loader, catalog = _loader()

    assert loader.execute(parse_descriptor(_descriptor("zones-a8-2"))) is True

    entries = catalog.zone_entries()
    assert sorted(entries) == ["vaga-12", "vaga-13"]
    assert entries["vaga-12"].space_id == "patio-1"
    assert entries["vaga-12"].artifact.artifact_version == "zones-a8-2"
    assert entries["vaga-12"].zone.max_occupancy == 1


def test_deve_carregar_calibracao_pelo_descritor_com_a_camera_do_artifact_id():
    loader, catalog = _loader()

    loader.execute(parse_descriptor(_descriptor("cal-cam0-3")))

    calibration = catalog.calibration("cam0")
    assert calibration.space_id == "patio-1"
    assert calibration.valid_from == datetime(2026, 9, 20, 9)


def test_deve_recusar_conteudo_que_nao_confere_com_o_hash():
    loader, catalog = _loader(**{"zones-a8-2.json": b'{"adulterado": true}'})

    with pytest.raises(ArtifactUnavailableError):
        loader.execute(parse_descriptor(_descriptor("zones-a8-2")))
    assert catalog.zone_entries() == {}


def test_deve_ignorar_artefato_de_tipo_que_o_s5_nao_usa():
    loader, catalog = _loader()
    rules = {**_descriptor("zones-a8-2"), "kind": "RULES", "artifact_id": "rules-a5"}

    assert loader.execute(parse_descriptor(rules)) is False
    assert catalog.versions() == {}


def test_versao_nova_substitui_a_anterior_do_mesmo_artefato():
    loader, catalog = _loader()
    loader.execute(parse_descriptor(_descriptor("zones-a8-2")))
    content = json.loads((ARTIFACTS / "zones-a8-2.json").read_text())
    content["zones"] = content["zones"][:1]

    catalog.put_zones(parse_zones(content, "zones-a8", "zones-a8-3"))

    assert sorted(catalog.zone_entries()) == ["vaga-12"]
    assert catalog.versions() == {"zones-a8": "zones-a8-3"}


@pytest.mark.parametrize("field", ["uri", "hash_sha256", "valid_from"])
def test_descritor_sem_campo_obrigatorio_e_recusado(field):
    descriptor = _descriptor("zones-a8-2")
    del descriptor[field]
    with pytest.raises(InvalidArtifactError):
        parse_descriptor(descriptor)


def test_zonas_sem_campo_obrigatorio_sao_recusadas():
    content = json.loads((ARTIFACTS / "zones-a8-2.json").read_text())
    del content["zones"][0]["exit_hysteresis_ms"]
    with pytest.raises(InvalidArtifactError):
        parse_zones(content, "zones-a8", "zones-a8-2")


def _handler():
    loader, catalog = _loader()
    return HandleArtifactMessageUseCase(loader, catalog, MessageDeduplicator()), catalog


def _published(name: str, message_id: str = "a1b2c3d4-0000-4000-8000-000000000001") -> dict:
    return {
        "message_type": "event", "message_id": message_id, "schema": "ods.artifact.published",
        "schema_version": "1.0", "producer": "A8", "published_at": "2026-09-23T14:00:00.000Z",
        "payload": _descriptor(name),
    }


def _calibration_event() -> dict:
    content = json.loads((ARTIFACTS / "cal-cam0-3.json").read_text())
    content["reference_frame"]["space_id"] = "patio-2"
    return {
        "message_type": "event", "message_id": "a1b2c3d4-0000-4000-8000-000000000002", "schema": "ods.i3.calibration",
        "schema_version": "1.0", "producer": "I3", "published_at": "2026-09-23T14:00:00.000Z",
        "source_id": "cam0", "sequence": 0, "artifact_version": "cal-cam0-4", "payload": content,
    }


def test_anuncio_de_artefato_pelo_barramento_carrega_as_zonas():
    handler, catalog = _handler()

    assert handler.execute(_published("zones-a8-2")) is True
    assert handler.execute(_published("zones-a8-2")) is False  # repetida
    assert sorted(catalog.zone_entries()) == ["vaga-12", "vaga-13"]


def test_evento_de_calibracao_traz_o_conteudo_no_payload():
    handler, catalog = _handler()

    handler.execute(_calibration_event())

    assert catalog.calibration("cam0").artifact_version == "cal-cam0-4"
    assert catalog.calibration("cam0").space_id == "patio-2"


def test_evento_de_calibracao_exige_source_id():
    handler, _ = _handler()
    message = _calibration_event()
    del message["source_id"]
    with pytest.raises(MalformedEventEnvelopeError):
        handler.execute(message)
