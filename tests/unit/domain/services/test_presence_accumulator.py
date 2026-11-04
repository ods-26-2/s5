from datetime import datetime, timedelta

import pytest

from src.domain.entities.position_sample import PositionSample, TrackPosition
from src.domain.exceptions import InvalidPositionError
from src.domain.services.presence_accumulator import PresenceAccumulator

BASE = datetime(2026, 9, 23, 14, 0, 0)


def _sample(offset_s: float, *positions: TrackPosition, session_id="s-1", source_id="cam0", fused=False) -> PositionSample:
    return PositionSample(
        source_id=source_id, session_id=session_id, observed_at=BASE + timedelta(seconds=offset_s),
        frame_index=int(offset_s * 30), positions=positions, fused=fused,
    )


def _entity(x: float, y: float, entity_id="e-1") -> TrackPosition:
    return TrackPosition(entity_id, "person", point_px=None, position_m=(x, y), space_id="patio-1")


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


def test_com_entidades_fundidas_a_mesma_pessoa_vista_por_duas_cameras_conta_uma_vez():
    accumulator = PresenceAccumulator()
    for offset in (0.0, 0.5, 1.0):
        accumulator.observe(_sample(offset, _metric(1.0, 1.0, "t-cam0")))
        accumulator.observe(_sample(offset, _metric(1.0, 1.0, "t-cam1"), source_id="cam1"))
        accumulator.observe(_sample(offset, _entity(1.0, 1.0), source_id="S2", fused=True))

    cells = _cells(accumulator.drain("s-1", BASE + timedelta(minutes=1)))

    # Só as câmeras antes da 1ª entidade (0,0 s) contam; dali em diante, só a entidade.
    assert cells == {("METERS", "patio-1", 10, 10): 1.0}


def test_entidades_nao_afetam_a_presenca_em_pixels_nem_outros_espacos():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _entity(1.0, 1.0), source_id="S2", fused=True))
    for offset in (0.0, 1.0):
        accumulator.observe(_sample(offset, _pixel(505, 702, "t-px")))
        accumulator.observe(_sample(offset, TrackPosition("t-2", "person", point_px=(1, 1), position_m=(1.0, 1.0), space_id="quadra-1")))

    cells = _cells(accumulator.drain("s-1", BASE + timedelta(minutes=1)))

    assert cells == {("PIXELS", "cam0", 50, 70): 1.0, ("METERS", "quadra-1", 10, 10): 1.0}


def test_entidade_sem_posicao_em_metros_e_ignorada():
    accumulator = PresenceAccumulator()
    for offset in (0.0, 1.0):
        accumulator.observe(_sample(offset, TrackPosition("e-1", "person", point_px=(1, 1)), source_id="S2", fused=True))
        accumulator.observe(_sample(offset, _metric(1.0, 1.0)))

    assert _cells(accumulator.drain("s-1", BASE + timedelta(minutes=1))) == {("METERS", "patio-1", 10, 10): 1.0}


def test_nova_sessao_volta_a_usar_as_cameras_ate_chegar_entidade():
    accumulator = PresenceAccumulator()
    accumulator.observe(_sample(0.0, _entity(1.0, 1.0), source_id="S2", fused=True))
    accumulator.forget_tracks("s-1")
    for offset in (0.0, 1.0):
        accumulator.observe(_sample(offset, _metric(1.0, 1.0), session_id="s-2"))

    assert len(accumulator.drain(None, BASE + timedelta(minutes=1))) == 1


def test_posicao_sem_pixels_nem_metros_e_recusada():
    with pytest.raises(InvalidPositionError):
        TrackPosition("t-1", "person", point_px=None)
