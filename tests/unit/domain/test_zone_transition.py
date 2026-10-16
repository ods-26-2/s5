from datetime import datetime

import pytest

from src.domain.entities.zone_transition import ZoneTransition
from src.domain.exceptions import InvalidZoneTransitionError

AT = datetime(2026, 9, 23, 14, 29, 59)


def _transition(**overrides) -> ZoneTransition:
    fields = dict(
        zone_id="vaga-12",
        track_id="t-0391",
        object_class="vehicle",
        transition="ENTER",
        occurred_at=AT,
        entered_at=AT,
        source_id="cam0",
        session_id="s-1",
    )
    fields.update(overrides)
    return ZoneTransition(**fields)


def test_deve_criar_entrada_sem_dwell_s():
    assert _transition().dwell_s is None


def test_deve_rejeitar_sentido_desconhecido():
    with pytest.raises(InvalidZoneTransitionError):
        _transition(transition="enter")


def test_deve_exigir_dwell_s_em_exit():
    with pytest.raises(InvalidZoneTransitionError):
        _transition(transition="EXIT")


def test_deve_rejeitar_dwell_s_negativo():
    with pytest.raises(InvalidZoneTransitionError):
        _transition(transition="EXIT", dwell_s=-1)


def test_deve_rejeitar_zone_id_vazio():
    with pytest.raises(InvalidZoneTransitionError):
        _transition(zone_id="")
