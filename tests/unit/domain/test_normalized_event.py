from datetime import datetime
from dataclasses import FrozenInstanceError

import pytest

from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.domain.exceptions import InvalidNormalizedEventError


def test_deve_criar_evento_quando_dados_forem_validos():
    event = NormalizedEvent(
        event_type="enter",
        origin="camera-01",
        coords=WorldCoordinate(x=1.0, y=2.0),
        timestamp=datetime(2026, 9, 10, 10, 0, 0),
    )
    assert event.event_type == "enter"
    assert event.origin == "camera-01"


def test_deve_lancar_excecao_quando_event_type_for_vazio():
    with pytest.raises(InvalidNormalizedEventError):
        NormalizedEvent(
            event_type="",
            origin="camera-01",
            coords=WorldCoordinate(x=0.0, y=0.0),
            timestamp=datetime(2026, 9, 10, 10, 0, 0),
        )


def test_deve_lancar_excecao_quando_origin_for_vazio():
    with pytest.raises(InvalidNormalizedEventError):
        NormalizedEvent(
            event_type="enter",
            origin="   ",
            coords=WorldCoordinate(x=0.0, y=0.0),
            timestamp=datetime(2026, 9, 10, 10, 0, 0),
        )


def test_deve_ser_imutavel_quando_tentar_alterar_event_type():
    event = NormalizedEvent(
        event_type="enter",
        origin="camera-01",
        coords=WorldCoordinate(x=0.0, y=0.0),
        timestamp=datetime(2026, 9, 10, 10, 0, 0),
    )
    with pytest.raises(FrozenInstanceError):
        event.event_type = "exit"
