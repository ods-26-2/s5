import hashlib
import json

import pytest

from src.domain.exceptions import ArtifactUnavailableError
from src.infrastructure.artifacts.file_artifact_source import FileArtifactSource, read_descriptor_files


def test_deve_mapear_registry_para_o_diretorio_do_registro(tmp_path):
    (tmp_path / "a8" / "zones").mkdir(parents=True)
    (tmp_path / "a8" / "zones" / "2").write_bytes(b"{}")

    assert FileArtifactSource(registry_dir=tmp_path).fetch("registry://a8/zones/2") == b"{}"


def test_deve_ler_file_uri_e_caminho_relativo(tmp_path):
    (tmp_path / "z.json").write_bytes(b"x")
    source = FileArtifactSource(base_dir=tmp_path)

    assert source.fetch((tmp_path / "z.json").as_uri()) == b"x"
    assert source.fetch("z.json") == b"x"


@pytest.mark.parametrize("uri", ["registry://../segredo", "registry://a8/../../segredo", "https://x/y", "../fora.json"])
def test_deve_recusar_uri_fora_do_diretorio_ou_de_esquema_nao_suportado(tmp_path, uri):
    with pytest.raises(ArtifactUnavailableError):
        FileArtifactSource(registry_dir=tmp_path / "reg", base_dir=tmp_path / "base").fetch(uri)


def test_registry_sem_diretorio_configurado_explica_o_que_falta():
    with pytest.raises(ArtifactUnavailableError, match="S5_ARTIFACT_REGISTRY_DIR"):
        FileArtifactSource().fetch("registry://a8/zones/2")


def test_arquivo_ausente_vira_artefato_indisponivel(tmp_path):
    with pytest.raises(ArtifactUnavailableError):
        FileArtifactSource(base_dir=tmp_path).fetch("nao-existe.json")


def test_descritor_com_uri_relativa_aponta_para_o_proprio_diretorio(tmp_path):
    content = b'{"a": 1}'
    (tmp_path / "zones.json").write_bytes(content)
    descriptor_path = tmp_path / "zones.descriptor.json"
    descriptor_path.write_text(json.dumps({"uri": "zones.json", "hash_sha256": hashlib.sha256(content).hexdigest()}))

    [descriptor] = read_descriptor_files([descriptor_path])

    assert FileArtifactSource().fetch(descriptor["uri"]) == content
