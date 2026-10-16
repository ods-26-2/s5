from dataclasses import dataclass, field
from datetime import datetime

from src.application.use_cases.ingest_envelope_use_case import IngestedMessage
from src.domain.entities.qualified_event import ENDED, QualifiedEvent
from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ZoneTransition


@dataclass
class ZoneContext:
    """O que se sabe de uma zona pelas últimas mensagens de S1: câmera e versão de ZONES."""

    source_id: str
    artifact_version: str


@dataclass
class MetricsBuffer:
    """Mensagens aceitas que ainda podem cair em uma janela aberta, mais o contexto que
    vai no envelope das métricas publicadas."""

    transitions: list[ZoneTransition] = field(default_factory=list)
    samples: list[ZoneOccupancySample] = field(default_factory=list)
    events: list[QualifiedEvent] = field(default_factory=list)
    zones: dict[str, ZoneContext] = field(default_factory=dict)
    rules_versions: dict[str, str] = field(default_factory=dict)
    current_session_id: str | None = None

    def add(self, ingested: IngestedMessage) -> None:
        envelope, message = ingested.envelope, ingested.message
        self.current_session_id = envelope.session_id
        if isinstance(message, QualifiedEvent):
            self.events.append(message)
            if envelope.artifact_version:
                self.rules_versions[message.event_type] = envelope.artifact_version
            return

        if isinstance(message, ZoneTransition):
            self.transitions.append(message)
        else:
            self.samples.append(message)
        self.zones[message.zone_id] = ZoneContext(
            source_id=envelope.source_id, artifact_version=envelope.artifact_version
        )

    def prune(self, before: datetime) -> None:
        """Descarta o que ficou antes de `before`, preservando a última amostra de ocupação
        de cada zona (ela é a contagem vigente no início da próxima janela) e todo evento
        de S2 ainda não encerrado, cujo started_at pode ser antigo."""
        self.transitions = [t for t in self.transitions if t.occurred_at >= before]

        last_sample_before: dict[str, ZoneOccupancySample] = {}
        for sample in sorted(self.samples, key=lambda s: s.observed_at):
            if sample.observed_at < before:
                last_sample_before[sample.zone_id] = sample
        self.samples = list(last_sample_before.values()) + [
            s for s in self.samples if s.observed_at >= before
        ]

        ended_ids = {e.event_id for e in self.events if e.phase == ENDED and e.occurred_at < before}
        self.events = [
            e for e in self.events if e.occurred_at >= before or e.event_id not in ended_ids
        ]
