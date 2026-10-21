from datetime import datetime, timedelta

import pytest

from src.domain.entities.position_sample import PositionSample, TrackPosition
from src.domain.exceptions import InvalidPositionError
from src.domain.services.presence_accumulator import PresenceAccumulator

BASE = datetime(2026, 9, 23, 14, 0, 0)


def _sample(offset_s: float, *positions: TrackPosition, session_id="s-1", source_id="cam0") -> PositionSample:
    return PositionSample(
        source_id=source_id, session_id=session_id, observed_at=BASE + timedelta(seconds=offset_s),
        frame_index=int(offset_s * 30), positions=positions,
    )


def _metric(x: float, y: float, track_id="t-1", object_class="person") -> TrackPosition:
    return TrackPosition(track_id, object_class, point_px=(500, 700), position_m=(x, y), space_id="patio-1")


def _pixel(x: float, y: float, track_id="t-1") -> TrackPosition:
    return TrackPosition(track_id, "person", point_px=(x, y))


def _cells(drained):
    return {(k.space_kind, k.space_key, k.cell_x, k.cell_y): round(v, 6) for k, v in drained.items()}


def test_deve_atribuir_o_intervalo_a_celula_da_posicao_anterior():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _metric(3.42, 7.10)))
    accumulator.observe(_sample(0.5, _metric(3.55, 7.10)))

    assert _cells(accumulator.drain("s-1", BASE + timedelta(minutes=1))) == {("METERS", "patio-1", 34, 71): 0.5}


def test_deve_descartar_intervalo_acima_do_limite_de_lacuna():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _metric(1.0, 1.0)))
    accumulator.observe(_sample(5.0, _metric(1.0, 1.0)))

    assert accumulator.drain("s-1", BASE + timedelta(minutes=1)) == {}


def test_deve_usar_pixels_por_camera_quando_nao_ha_calibracao():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _pixel(505, 702)))
    accumulator.observe(_sample(1.0, _pixel(505, 702)))

    assert _cells(accumulator.drain("s-1", BASE + timedelta(minutes=1))) == {("PIXELS", "cam0", 50, 70): 1.0}


def test_rastros_e_cameras_diferentes_acumulam_separadamente():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _metric(1.0, 1.0, "t-1"), _metric(1.0, 1.0, "t-2")))
    accumulator.observe(_sample(0.2, _metric(1.0, 1.0, "t-1"), source_id="cam1"))
    accumulator.observe(_sample(0.4, _metric(1.0, 1.0, "t-1"), _metric(1.0, 1.0, "t-2")))

    assert _cells(accumulator.drain("s-1", BASE + timedelta(minutes=1))) == {("METERS", "patio-1", 10, 10): 0.8}


def test_so_entrega_minutos_fechados_da_sessao_corrente():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(59.0, _metric(1.0, 1.0)))
    accumulator.observe(_sample(59.5, _metric(1.0, 1.0)))
    accumulator.observe(_sample(60.0, _metric(1.0, 1.0)))

    assert len(accumulator.drain("s-1", BASE + timedelta(seconds=59.9))) == 0
    first = accumulator.drain("s-1", BASE + timedelta(minutes=1))
    assert [k.bucket_start for k in first] == [BASE]


def test_entrega_tudo_de_sessoes_que_nao_sao_a_corrente():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _metric(1.0, 1.0)))
    accumulator.observe(_sample(0.5, _metric(1.0, 1.0)))

    assert len(accumulator.drain("outra", BASE)) == 1


def test_esquecer_rastros_da_sessao_nao_liga_posicoes_de_sessoes_diferentes():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _metric(1.0, 1.0)))
    accumulator.forget_tracks("s-1")
    accumulator.observe(_sample(0.5, _metric(1.0, 1.0)))

    assert accumulator.drain(None, BASE + timedelta(hours=1)) == {}


def test_posicao_em_metros_exige_space_id():
    with pytest.raises(InvalidPositionError):
        TrackPosition("t-1", "person", point_px=(1, 1), position_m=(1.0, 1.0))
