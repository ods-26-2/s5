from datetime import datetime

from src.domain.services.moving_window_generator import MovingWindowGenerator


def test_deve_gerar_uma_janela_por_tamanho_informado():
    reference_time = datetime(2026, 9, 10, 10, 0, 0)
    windows = MovingWindowGenerator().generate(reference_time, sizes_seconds=[60, 900, 3600])

    assert len(windows) == 3
    assert all(window.end_time == reference_time for window in windows)


def test_deve_calcular_start_time_corretamente_para_cada_tamanho():
    reference_time = datetime(2026, 9, 10, 10, 0, 0)
    windows = MovingWindowGenerator().generate(reference_time, sizes_seconds=[60])

    assert windows[0].duration_seconds == 60.0
