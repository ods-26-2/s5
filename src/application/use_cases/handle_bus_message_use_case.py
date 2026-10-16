from src.application.state.metrics_buffer import MetricsBuffer
from src.application.use_cases.ingest_envelope_use_case import IngestEnvelopeUseCase


class HandleBusMessageUseCase:
    """Ponto de entrada de cada mensagem assinada: ingere e guarda no buffer das janelas.
    Retorna False quando a mensagem é repetida ou pertence a uma sessão já encerrada;
    erros de contrato sobem para o chamador."""

    def __init__(self, ingest: IngestEnvelopeUseCase, buffer: MetricsBuffer) -> None:
        self._ingest = ingest
        self._buffer = buffer

    @property
    def supported_schemas(self) -> tuple[str, ...]:
        return self._ingest.supported_schemas

    def execute(self, raw_message: dict) -> bool:
        ingested = self._ingest.execute(raw_message)
        if ingested is None:
            return False
        return self._buffer.add(ingested)
