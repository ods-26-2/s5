from datetime import datetime

import pytest

from src.domain.exceptions import InvalidGranularityError
from src.domain.value_objects.granularity import closed_windows


def test_deve_alinhar_janelas_ao_relogio():
    windows = closed_windows("15m", datetime(2026, 9, 23, 14, 7), datetime(2026, 9, 23, 14, 31))
    assert [(w.start_time, w.end_time) for w in windows] == [
        (datetime(2026, 9, 23, 14, 0), datetime(2026, 9, 23, 14, 15)),
        (datetime(2026, 9, 23, 14, 15), datetime(2026, 9, 23, 14, 30)),
    ]


def test_deve_incluir_janela_que_termina_exatamente_no_limite_superior():
    windows = closed_windows("1m", datetime(2026, 9, 23, 14, 0, 30), datetime(2026, 9, 23, 14, 1))
    assert [w.end_time for w in windows] == [datetime(2026, 9, 23, 14, 1)]


def test_nao_deve_repetir_janela_que_termina_no_limite_inferior():
    windows = closed_windows("1m", datetime(2026, 9, 23, 14, 1), datetime(2026, 9, 23, 14, 1, 30))
    assert windows == []


def test_deve_alinhar_janela_diaria_a_meia_noite_utc():
    windows = closed_windows("1d", datetime(2026, 9, 23, 23, 59), datetime(2026, 9, 24, 0, 0, 5))
    assert windows[0].start_time == datetime(2026, 9, 23)


def test_deve_rejeitar_granularidade_fora_do_enum():
    with pytest.raises(InvalidGranularityError):
        closed_windows("1s", datetime(2026, 9, 23), datetime(2026, 9, 24))
