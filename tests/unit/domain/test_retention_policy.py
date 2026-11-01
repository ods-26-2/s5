from datetime import datetime, timedelta

import pytest

from src.domain.value_objects.retention_policy import RetentionPolicy

NOW = datetime(2026, 10, 21, 12, 0)


def test_prazos_padrao_por_granularidade():
    policy = RetentionPolicy()
    assert policy.metric_cutoff("1m", NOW) == NOW - timedelta(days=7)
    assert policy.metric_cutoff("1d", NOW) == NOW - timedelta(days=1825)
    assert policy.presence_cutoff(NOW) == NOW - timedelta(days=14)
    assert policy.replay_cutoff(NOW) == NOW - timedelta(days=7)


def test_granularidade_fora_da_politica_nao_expira():
    assert RetentionPolicy(metric_days={"1m": 1}).metric_cutoff("1h", NOW) is None


@pytest.mark.parametrize(
    "fields", [{"metric_days": {"5m": 1}}, {"metric_days": {"1m": 0}}, {"presence_days": 0}, {"replay_days": -1}]
)
def test_deve_rejeitar_politica_invalida(fields):
    with pytest.raises(ValueError):
        RetentionPolicy(**fields)
