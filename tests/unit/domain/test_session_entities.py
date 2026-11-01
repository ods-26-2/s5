from datetime import datetime

import pytest

from src.domain.entities.replay_state import ReplayState
from src.domain.entities.session_start import SessionStart
from src.domain.exceptions import InvalidSessionError

AT = datetime(2026, 9, 23, 14, 29, 58)


@pytest.mark.parametrize("field,value", [("mode", "TEST"), ("reason", "PAUSE"), ("session_id", " ")])
def test_deve_rejeitar_inicio_de_sessao_invalido(field, value):
    fields = dict(session_id="s-1", mode="LIVE", started_at=AT)
    fields[field] = value
    with pytest.raises(InvalidSessionError):
        SessionStart(**fields)


@pytest.mark.parametrize("field,value", [("state", "SEEKING"), ("position_ms", -1), ("speed_factor", 0.0)])
def test_deve_rejeitar_estado_de_replay_invalido(field, value):
    fields = dict(
        session_id="s-1", captured_at=AT, recording_id="rec-1", state="PLAYING",
        position_ms=0, duration_ms=1000, speed_factor=1.0, loop=False,
    )
    fields[field] = value
    with pytest.raises(InvalidSessionError):
        ReplayState(**fields)
