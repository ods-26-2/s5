from datetime import datetime, timedelta

import pytest

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.qualified_event import QualifiedEvent
from src.domain.exceptions import InvalidEventMetricError, InvalidQualifiedEventError
from src.domain.value_objects.time_window import TimeWindow

AT = datetime(2026, 9, 23, 14, 30)
WINDOW = TimeWindow(start_time=AT, end_time=AT + timedelta(hours=1))


def _event(**overrides) -> QualifiedEvent:
    fields = dict(
        event_id="ev-1", event_type="PPE_NON_COMPLIANT", status="CONFIRMED", phase="STARTED",
        started_at=AT, duration_ms=0, occurred_at=AT, session_id="s-1",
    )
    fields.update(overrides)
    return QualifiedEvent(**fields)


@pytest.mark.parametrize("field,value", [("status", "OK"), ("phase", "OPEN"), ("duration_ms", -1), ("event_id", "")])
def test_deve_rejeitar_evento_qualificado_invalido(field, value):
    with pytest.raises(InvalidQualifiedEventError):
        _event(**{field: value})


def test_deve_rejeitar_uncertain_count_maior_que_count():
    with pytest.raises(InvalidEventMetricError):
        EventMetric(event_type="X", window=WINDOW, count=1, uncertain_count=2)


def test_deve_rejeitar_event_type_vazio():
    with pytest.raises(InvalidEventMetricError):
        EventMetric(event_type=" ", window=WINDOW, count=0, uncertain_count=0)
