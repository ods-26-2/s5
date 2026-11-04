import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.application.ports.artifact_source import IArtifactSource
from src.domain.exceptions import ArtifactUnavailableError

REGISTRY_SCHEME = "registry"


class FileArtifactSource(IArtifactSource):
    """Lê artefatos do disco enquanto o registro de B5 não tem formato definido.

    - registry://a8/zones/2 → <registry_dir>/a8/zones/2
    - file:///caminho/absoluto → o próprio arquivo
    - caminho sem esquema → relativo a base_dir

    Caminhos que saiam do diretório de origem (por .. ou link) são recusados.
    """

    def __init__(self, registry_dir: Path | None = None, base_dir: Path | None = None) -> None:
        self._registry_dir = registry_dir.resolve() if registry_dir else None
        self._base_dir = (base_dir or Path.cwd()).resolve()

    def fetch(self, uri: str) -> bytes:
        path = self._resolve(uri)
        try:
            return path.read_bytes()
        except OSError as error:
            raise ArtifactUnavailableError(f"Não foi possível ler o artefato {uri}: {error.strerror}.") from error

    def _resolve(self, uri: str) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme == REGISTRY_SCHEME:
            if self._registry_dir is None:
                raise ArtifactUnavailableError(
                    f"{uri}: defina o diretório do registro (S5_ARTIFACT_REGISTRY_DIR) para ler registry://."
                )
            return self._inside(self._registry_dir, parsed.netloc + unquote(parsed.path), uri)
        if parsed.scheme == "file":
            return Path(unquote(parsed.path))
        if parsed.scheme:
            raise ArtifactUnavailableError(f"Esquema de URI não suportado para artefatos: {uri}.")
        return self._inside(self._base_dir, uri, uri)

    @staticmethod
    def _inside(root: Path, relative: str, uri: str) -> Path:
        path = (root / relative.lstrip("/")).resolve()
        if not path.is_relative_to(root):
            raise ArtifactUnavailableError(f"{uri} aponta para fora de {root}.")
        return path


def read_descriptor_files(paths: list[Path]) -> list[dict]:
    """Lê os descritores de artefato fixados na build. Uma URI sem esquema é relativa ao
    diretório do próprio descritor, para que descritor e conteúdo viajem juntos."""
    descriptors = []
    for path in paths:
        try:
            descriptor = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ArtifactUnavailableError(f"Não foi possível ler o descritor {path}: {error}.") from error
        uri = descriptor.get("uri") if isinstance(descriptor, dict) else None
        if isinstance(uri, str) and uri and not urlparse(uri).scheme:
            descriptor = {**descriptor, "uri": (path.parent / uri).resolve().as_uri()}
        descriptors.append(descriptor)
    return descriptors
