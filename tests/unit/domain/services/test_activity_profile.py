from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.services.activity_profile import (
    DAY_OF_MONTH,
    DAY_OF_WEEK,
    HOUR_OF_DAY,
    bucket_of,
    event_profile,
    peak_bucket,
    zone_profile,
)
from src.domain.value_objects.time_window import TimeWindow

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def _zone(start: datetime, total: int, peak: int = 1, avg: float = 0.5) -> OccupancyMetric:
    window = TimeWindow(start_time=start, end_time=start + timedelta(hours=1))
    return OccupancyMetric(zone_id="vaga-12", window=window, dwell_time_avg=1.0, occupancy_peak=peak,
                           total_count=total, occupancy_avg=avg)


def test_hora_do_dia_usa_o_fuso_pedido():
    # 02:00 UTC de 24/9 é 23:00 de 23/9 em São Paulo.
    start = datetime(2026, 9, 24, 2, 0)
    assert bucket_of(start, HOUR_OF_DAY, timezone.utc) == 2
    assert bucket_of(start, HOUR_OF_DAY, SAO_PAULO) == 23
    assert bucket_of(start, DAY_OF_MONTH, SAO_PAULO) == 23
    assert bucket_of(start, DAY_OF_WEEK, SAO_PAULO) == 3  # quarta-feira


def test_perfil_por_hora_soma_os_dias_e_acha_o_pico():
    metrics = [
        _zone(datetime(2026, 9, 22, 21), total=3, peak=1, avg=0.2),
        _zone(datetime(2026, 9, 23, 21), total=5, peak=3, avg=0.6),
        _zone(datetime(2026, 9, 23, 14), total=4, peak=2, avg=1.0),
    ]

    buckets = zone_profile(metrics, HOUR_OF_DAY, SAO_PAULO)

    by_hour = {b.bucket: b for b in buckets}
    assert sorted(by_hour) == [11, 18]
    assert (by_hour[18].windows, by_hour[18].total, by_hour[18].occupancy_peak) == (2, 8, 3)
    assert abs(by_hour[18].occupancy_avg - 0.4) < 1e-9
    assert peak_bucket(buckets) == 18


def test_perfil_de_eventos_soma_tipos_diferentes_na_mesma_janela():
    start = datetime(2026, 9, 23, 14)
    window = TimeWindow(start_time=start, end_time=start + timedelta(hours=1))
    metrics = [
        EventMetric(event_type="A", window=window, count=2, uncertain_count=1),
        EventMetric(event_type="B", window=window, count=3, uncertain_count=0),
    ]

    [bucket] = event_profile(metrics, DAY_OF_WEEK, timezone.utc)

    assert (bucket.bucket, bucket.windows, bucket.total, bucket.uncertain) == (3, 1, 5, 1)


def test_sem_atividade_nao_ha_pico_e_empate_fica_com_o_primeiro():
    assert peak_bucket(zone_profile([_zone(datetime(2026, 9, 23, 14), total=0)], HOUR_OF_DAY, timezone.utc)) is None
    assert peak_bucket([]) is None
    tie = zone_profile(
        [_zone(datetime(2026, 9, 23, 9), total=2), _zone(datetime(2026, 9, 23, 7), total=2)], HOUR_OF_DAY, timezone.utc
    )
    assert peak_bucket(tie) == 7
