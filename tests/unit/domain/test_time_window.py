from datetime import datetime, timedelta
from dataclasses import FrozenInstanceError

import pytest

from src.domain.value_objects.time_window import TimeWindow
from src.domain.exceptions import InvalidTimeWindowError


def test_deve_calcular_duracao_corretamente_quando_janela_for_valida():
    start = datetime(2026, 9, 10, 10, 0, 0)
    end = start + timedelta(seconds=30)
    tw = TimeWindow(start_time=start, end_time=end)
    assert tw.duration_seconds == 30.0


def test_deve_lancar_excecao_quando_start_for_maior_ou_igual_ao_end():
    start = datetime(2026, 9, 10, 10, 0, 0)
    end = start - timedelta(seconds=1)
    with pytest.raises(InvalidTimeWindowError):
        TimeWindow(start_time=start, end_time=end)


def test_deve_ser_imutavel_quando_tentar_alterar_start():
    tw = TimeWindow(
        start_time=datetime(2026, 9, 10, 10, 0, 0),
        end_time=datetime(2026, 9, 10, 10, 0, 30),
    )
    with pytest.raises(FrozenInstanceError):
        tw.start_time = datetime(2026, 1, 1)