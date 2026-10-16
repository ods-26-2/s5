from datetime import datetime

import pytest

from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.exceptions import InvalidZoneOccupancyError


def _sample(**overrides) -> ZoneOccupancySample:
    fields = dict(
        zone_id="vaga-12",
        observed_at=datetime(2026, 9, 23, 14, 29, 59),
        count=1,
        source_id="cam0",
        session_id="s-1",
    )
    fields.update(overrides)
    return ZoneOccupancySample(**fields)


def test_deve_criar_amostra_valida():
    assert _sample(count_by_class={"vehicle": 1}).count == 1


def test_deve_rejeitar_contagem_negativa():
    with pytest.raises(InvalidZoneOccupancyError):
        _sample(count=-1)


def test_deve_rejeitar_contagem_por_classe_negativa():
    with pytest.raises(InvalidZoneOccupancyError):
        _sample(count_by_class={"vehicle": -1})


def test_deve_rejeitar_zone_id_vazio():
    with pytest.raises(InvalidZoneOccupancyError):
        _sample(zone_id=" ")
