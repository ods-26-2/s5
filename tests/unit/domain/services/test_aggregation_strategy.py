from datetime import datetime, timedelta

import pytest

from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ZoneTransition
from src.domain.services.aggregation_strategy import ZoneOccupancyAggregationStrategy
from src.domain.value_objects.time_window import TimeWindow

BASE_TIME = datetime(2026, 9, 10, 10, 0, 0)
WINDOW = TimeWindow(start_time=BASE_TIME, end_time=BASE_TIME + timedelta(minutes=1))


def _transition(transition: str, offset_s: float, dwell_s: int | None = None, zone_id: str = "zone-01"):
    occurred_at = BASE_TIME + timedelta(seconds=offset_s)
    return ZoneTransition(
        zone_id=zone_id,
        track_id="t-1",
        object_class="person",
        transition=transition,
        occurred_at=occurred_at,
        entered_at=occurred_at - timedelta(seconds=dwell_s or 0),
        source_id="cam0",
        session_id="s-1",
        dwell_s=dwell_s,
    )


def _sample(offset_s: float, count: int, zone_id: str = "zone-01") -> ZoneOccupancySample:
    return ZoneOccupancySample(
        zone_id=zone_id,
        observed_at=BASE_TIME + timedelta(seconds=offset_s),
        count=count,
        source_id="cam0",
        session_id="s-1",
    )


def _aggregate(transitions=(), samples=()):
    return ZoneOccupancyAggregationStrategy().aggregate(
        list(transitions), list(samples), zone_id="zone-01", window=WINDOW
    )


def test_deve_calcular_dwell_time_medio_pelo_dwell_s_das_saidas():
    metric = _aggregate([_transition("EXIT", 10, dwell_s=10), _transition("EXIT", 40, dwell_s=20)])
    assert metric.dwell_time_avg == 15.0


def test_deve_contar_entradas_como_total_count():
    metric = _aggregate([_transition("ENTER", 5), _transition("ENTER", 15), _transition("EXIT", 20, 5)])
    assert metric.total_count == 2


def test_deve_retornar_dwell_time_zero_quando_nao_houver_saidas():
    metric = _aggregate([_transition("ENTER", 5)])
    assert metric.dwell_time_avg == 0.0


def test_deve_ignorar_transicoes_de_outras_zonas_e_fora_da_janela():
    metric = _aggregate(
        [
            _transition("ENTER", 5, zone_id="zone-02"),
            _transition("ENTER", -1),
            _transition("ENTER", 60),
        ]
    )
    assert metric.total_count == 0


def test_deve_calcular_pico_pela_maior_contagem_vigente():
    metric = _aggregate(samples=[_sample(10, 2), _sample(20, 5), _sample(30, 1)])
    assert metric.occupancy_peak == 5


def test_deve_calcular_ocupacao_media_ponderada_pelo_tempo():
    # 0 em [0, 15), 2 em [15, 45), 1 em [45, 60) -> (2*30 + 1*15) / 60 = 1.25
    metric = _aggregate(samples=[_sample(15, 2), _sample(45, 1)])
    assert metric.occupancy_avg == pytest.approx(1.25)


def test_deve_herdar_contagem_da_ultima_amostra_anterior_a_janela():
    metric = _aggregate(samples=[_sample(-30, 3), _sample(-10, 4)])
    assert metric.occupancy_peak == 4
    assert metric.occupancy_avg == pytest.approx(4.0)


def test_deve_considerar_zona_vazia_sem_nenhuma_amostra():
    metric = _aggregate()
    assert metric.occupancy_peak == 0
    assert metric.occupancy_avg == 0.0
