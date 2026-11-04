from abc import ABC, abstractmethod


class IArtifactSource(ABC):
    """Porta de leitura do conteúdo de um artefato pela URI do descritor comum. O formato
    do registro de B5 ainda não foi definido; quando for, basta um adaptador novo."""

    @abstractmethod
    def fetch(self, uri: str) -> bytes: ...
