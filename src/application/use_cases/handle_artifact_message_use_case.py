from src.application.parsers.artifact_parser import parse_calibration, parse_descriptor
from src.application.parsers.envelope_parser import parse_envelope
from src.application.state.artifact_catalog import ArtifactCatalog
from src.application.use_cases.load_artifact_use_case import LoadArtifactUseCase
from src.domain.exceptions import UnsupportedSchemaError, UnsupportedSchemaVersionError
from src.domain.services.message_deduplicator import MessageDeduplicator

ARTIFACT_PUBLISHED_SCHEMA = "ods.artifact.published"
CALIBRATION_SCHEMA = "ods.i3.calibration"
SUPPORTED_MAJOR_VERSION = 1
# ods.i3.calibration: EV-SINAL sem captured_at e session_id (Especificação 1.0, seção 6).
CALIBRATION_FIELDS = ("source_id", "sequence", "artifact_version")


class HandleArtifactMessageUseCase:
    """Atualiza os artefatos do S5 a partir do barramento (Especificação 1.0, seção 8):

    - ods.artifact.published anuncia uma versão nova; o S5 busca o conteúdo pela URI e o
      confere pelo hash. O perfil é EV-SERVIÇO sem campos de sinal, então só os campos
      fixos do envelope são exigidos;
    - ods.i3.calibration já traz o conteúdo da calibração no payload.

    Fica separado da ingestão de métricas porque estas mensagens não pertencem a uma
    sessão de captura e não podem mexer no estado das janelas.
    """

    def __init__(
        self, loader: LoadArtifactUseCase, catalog: ArtifactCatalog, deduplicator: MessageDeduplicator
    ) -> None:
        self._loader = loader
        self._catalog = catalog
        self._deduplicator = deduplicator

    @property
    def supported_schemas(self) -> tuple[str, ...]:
        return (ARTIFACT_PUBLISHED_SCHEMA, CALIBRATION_SCHEMA)

    def execute(self, raw_message: dict) -> bool:
        schema = raw_message.get("schema")
        if schema not in self.supported_schemas:
            raise UnsupportedSchemaError(f"Schema não tratado como artefato pelo S5: {schema!r}.")
        required = CALIBRATION_FIELDS if schema == CALIBRATION_SCHEMA else ()
        envelope = parse_envelope(raw_message, required_fields=required)
        if self._deduplicator.is_duplicate(envelope.message_id):
            return False
        if envelope.schema_major != SUPPORTED_MAJOR_VERSION:
            raise UnsupportedSchemaVersionError(
                f"{envelope.schema} {envelope.schema_version}: S5 conhece só o MAJOR {SUPPORTED_MAJOR_VERSION}."
            )

        if schema == CALIBRATION_SCHEMA:
            self._catalog.put_calibration(
                parse_calibration(envelope.payload, envelope.source_id, envelope.artifact_version)
            )
            changed = True
        else:
            changed = self._loader.execute(parse_descriptor(envelope.payload))
        self._deduplicator.register(envelope.message_id)
        return changed
