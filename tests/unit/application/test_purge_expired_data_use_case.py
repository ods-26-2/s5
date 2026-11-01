from datetime import datetime, timedelta

from src.application.use_cases.purge_expired_data_use_case import PurgeExpiredDataUseCase
from src.domain.value_objects.retention_policy import RetentionPolicy

from .fakes import FakeTimeSeriesRepository

NOW = datetime(2026, 10, 21, 12, 0)


def test_deve_pedir_ao_repositorio_cada_expurgo_com_o_prazo_da_politica():
    repository = FakeTimeSeriesRepository()
    policy = RetentionPolicy(metric_days={"1m": 2, "1h": 30}, presence_days=5, replay_days=1)

    removed = PurgeExpiredDataUseCase(repository, policy).execute(NOW)

    assert repository.purge_calls == [
        ("metrics", "1m", NOW - timedelta(days=2)),
        ("metrics", "1h", NOW - timedelta(days=30)),
        ("presence", None, NOW - timedelta(days=5)),
        ("replay", None, NOW - timedelta(days=1)),
    ]
    assert set(removed) == {"metrics_1m", "metrics_1h", "presence", "replay"}
