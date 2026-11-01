from datetime import datetime

from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.value_objects.retention_policy import RetentionPolicy


class PurgeExpiredDataUseCase:
    """Apaga do banco o que passou do prazo da política de retenção. Deve rodar com
    pouca frequência (ex.: a cada hora); cada execução apaga tudo o que já expirou."""

    def __init__(self, repository: ITimeSeriesRepository, policy: RetentionPolicy) -> None:
        self._repository = repository
        self._policy = policy

    def execute(self, now: datetime) -> dict[str, int]:
        """Devolve quantas linhas saíram de cada conjunto."""
        removed = {}
        for granularity in self._policy.metric_days:
            cutoff = self._policy.metric_cutoff(granularity, now)
            removed[f"metrics_{granularity}"] = self._repository.delete_live_metrics_before(
                granularity, cutoff
            )
        removed["presence"] = self._repository.delete_live_presence_before(
            self._policy.presence_cutoff(now)
        )
        removed["replay"] = self._repository.delete_replay_stored_before(
            self._policy.replay_cutoff(now)
        )
        return removed
