from dataclasses import dataclass, field
from datetime import datetime

from src.application.use_cases.ingest_envelope_use_case import IngestedMessage
from src.domain.entities.position_sample import PositionSample
from src.domain.entities.qualified_event import ENDED, QualifiedEvent
from src.domain.entities.replay_state import ReplayState
from src.domain.entities.session_start import LIVE, SessionStart
from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ZoneTransition
from src.domain.services.presence_accumulator import PresenceAccumulator


@dataclass
class ZoneContext:
    """O que se sabe de uma zona pelas últimas mensagens de S1: câmera e versão de ZONES."""

    source_id: str
    artifact_version: str


@dataclass
class SessionClock:
    """Sessão corrente e o seu relógio de captura.

    watermark é o maior captured_at já recebido na sessão. Em REPLAY, o tempo de captura é
    o da gravação, que não acompanha o relógio de parede; é o watermark que diz até onde
    as janelas podem fechar. P6 publica ods.p6.replay.state a cada 1 s em reprodução, o que
    mantém o watermark andando mesmo quando nenhuma zona muda.
    """

    session_id: str
    mode: str
    started_at: datetime
    watermark: datetime


@dataclass
class MetricsBuffer:
    """Mensagens aceitas que ainda podem cair em uma janela aberta, o contexto que vai no
    envelope das métricas publicadas e a sessão a que tudo isso pertence.

    Cada ods.session.started reinicia o estado (Especificação 1.0, seção 7): o que foi
    recebido na sessão anterior é descartado e mensagens atrasadas dela são ignoradas.
    Mensagens de S1 e S2 podem chegar antes do anúncio da sessão, porque os tópicos são
    independentes; nesse caso a sessão é adotada como LIVE e o anúncio, quando chegar,
    só completa o modo e o início, sem descartar o que já foi recebido.
    """

    transitions: list[ZoneTransition] = field(default_factory=list)
    samples: list[ZoneOccupancySample] = field(default_factory=list)
    events: list[QualifiedEvent] = field(default_factory=list)
    zones: dict[str, ZoneContext] = field(default_factory=dict)
    rules_versions: dict[str, str] = field(default_factory=dict)
    presence: PresenceAccumulator = field(default_factory=PresenceAccumulator)
    session: SessionClock | None = None
    ended_sessions: set[str] = field(default_factory=set)
    session_modes: dict[str, str] = field(default_factory=dict)

    @property
    def current_session_id(self) -> str | None:
        return self.session.session_id if self.session else None

    def mode_of(self, session_id: str) -> str:
        """Modo de uma sessão vista por este buffer; LIVE se ela nunca foi anunciada."""
        return self.session_modes.get(session_id, LIVE)

    def add(self, ingested: IngestedMessage) -> bool:
        """Guarda a mensagem; devolve False quando ela pertence a uma sessão encerrada."""
        envelope, message = ingested.envelope, ingested.message
        if envelope.session_id in self.ended_sessions:
            return False
        if isinstance(message, SessionStart):
            self._start_session(message)
            return True

        if self.session is None or envelope.session_id != self.session.session_id:
            self._switch_to(
                SessionClock(
                    session_id=envelope.session_id,
                    mode=LIVE,
                    started_at=envelope.captured_at,
                    watermark=envelope.captured_at,
                )
            )
        self.session.watermark = max(self.session.watermark, envelope.captured_at)

        if isinstance(message, ReplayState):
            return True
        if isinstance(message, PositionSample):
            self.presence.observe(message)
            return True
        if isinstance(message, QualifiedEvent):
            self.events.append(message)
            if envelope.artifact_version:
                self.rules_versions[message.event_type] = envelope.artifact_version
            return True

        if isinstance(message, ZoneTransition):
            self.transitions.append(message)
        else:
            self.samples.append(message)
        self.zones[message.zone_id] = ZoneContext(
            source_id=envelope.source_id, artifact_version=envelope.artifact_version
        )
        return True

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

    def _start_session(self, start: SessionStart) -> None:
        if start.previous_session_id:
            self.ended_sessions.add(start.previous_session_id)
        self.session_modes[start.session_id] = start.mode
        if self.session is not None and self.session.session_id == start.session_id:
            self.session.mode = start.mode
            self.session.started_at = min(self.session.started_at, start.started_at)
            self.session.watermark = max(self.session.watermark, start.started_at)
            return
        self._switch_to(
            SessionClock(
                session_id=start.session_id,
                mode=start.mode,
                started_at=start.started_at,
                watermark=start.started_at,
            )
        )

    def _switch_to(self, clock: SessionClock) -> None:
        if self.session is not None:
            self.ended_sessions.add(self.session.session_id)
            self.presence.forget_tracks(self.session.session_id)
        self.session_modes.setdefault(clock.session_id, clock.mode)
        self.transitions = []
        self.samples = []
        self.events = []
        self.session = clock
