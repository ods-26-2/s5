from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.domain.value_objects.granularity import GRANULARITY_SECONDS


def _default_metric_days() -> dict[str, int]:
    return {"1m": 7, "15m": 90, "1h": 365, "1d": 1825}


@dataclass(frozen=True)
class RetentionPolicy:
    """Por quanto tempo o S5 guarda cada tipo de dado.

    Métricas LIVE expiram pelo fim da janela, com prazo por granularidade: a série fina
    serve para o dia a dia, as grossas para comparar períodos longos. A presença por
    célula é o dado mais volumoso (uma linha por célula fina com movimento, por minuto) e
    tem prazo próprio. Dados de replay expiram pelo momento em que foram gravados, porque
    o tempo de captura deles é o da gravação reproduzida, que pode ser de dias atrás.

    Os prazos padrão são provisórios, até o orçamento de disco da Jetson ser fechado com
    o SIS-1 (P3).
    """

    metric_days: dict[str, int] = field(default_factory=_default_metric_days)
    presence_days: int = 14
    replay_days: int = 7

    def __post_init__(self) -> None:
        unknown = set(self.metric_days) - set(GRANULARITY_SECONDS)
        if unknown:
            raise ValueError(f"Granularidades desconhecidas na política: {sorted(unknown)}.")
        days = [*self.metric_days.values(), self.presence_days, self.replay_days]
        if any(value <= 0 for value in days):
            raise ValueError("Todo prazo de retenção deve ser maior que zero.")

    def metric_cutoff(self, granularity: str, now: datetime) -> datetime | None:
        """Janelas LIVE que terminaram antes deste instante expiram; None se a
        granularidade não tem prazo e é guardada indefinidamente."""
        days = self.metric_days.get(granularity)
        return now - timedelta(days=days) if days is not None else None

    def presence_cutoff(self, now: datetime) -> datetime:
        return now - timedelta(days=self.presence_days)

    def replay_cutoff(self, now: datetime) -> datetime:
        return now - timedelta(days=self.replay_days)
