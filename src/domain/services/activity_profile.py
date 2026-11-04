from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric

HOUR_OF_DAY = "HOUR_OF_DAY"
DAY_OF_WEEK = "DAY_OF_WEEK"
DAY_OF_MONTH = "DAY_OF_MONTH"
PROFILES = (HOUR_OF_DAY, DAY_OF_WEEK, DAY_OF_MONTH)


@dataclass(frozen=True)
class ProfileBucket:
    """Uma hora do dia (0–23), dia da semana (1 = segunda … 7 = domingo, ISO 8601) ou dia do
    mês (1–31), somando todas as janelas da série que começam nele. `total` é a soma de
    entradas (métricas por zona) ou de eventos (métricas por tipo de evento)."""

    bucket: int
    windows: int
    total: int
    occupancy_peak: int | None = None
    occupancy_avg: float | None = None
    uncertain: int | None = None


def bucket_of(window_start: datetime, by: str, zone: tzinfo) -> int:
    """Hora, dia da semana ou dia do mês do início da janela, no fuso pedido. As janelas
    são gravadas em UTC sem tzinfo; a mesma janela pode cair em outro dia no fuso local."""
    local = window_start.replace(tzinfo=timezone.utc).astimezone(zone)
    if by == HOUR_OF_DAY:
        return local.hour
    if by == DAY_OF_WEEK:
        return local.isoweekday()
    if by == DAY_OF_MONTH:
        return local.day
    raise ValueError(f"Perfil desconhecido: {by!r}.")


def zone_profile(metrics: list[OccupancyMetric], by: str, zone: tzinfo) -> list[ProfileBucket]:
    groups: dict[int, list[OccupancyMetric]] = defaultdict(list)
    for metric in metrics:
        groups[bucket_of(metric.window.start_time, by, zone)].append(metric)
    return [
        ProfileBucket(
            bucket=bucket,
            windows=len({m.window.start_time for m in group}),
            total=sum(m.total_count for m in group),
            occupancy_peak=max(m.occupancy_peak for m in group),
            occupancy_avg=sum(m.occupancy_avg for m in group) / len(group),
        )
        for bucket, group in sorted(groups.items())
    ]


def event_profile(metrics: list[EventMetric], by: str, zone: tzinfo) -> list[ProfileBucket]:
    groups: dict[int, list[EventMetric]] = defaultdict(list)
    for metric in metrics:
        groups[bucket_of(metric.window.start_time, by, zone)].append(metric)
    return [
        ProfileBucket(
            bucket=bucket,
            windows=len({m.window.start_time for m in group}),
            total=sum(m.count for m in group),
            uncertain=sum(m.uncertain_count for m in group),
        )
        for bucket, group in sorted(groups.items())
    ]


def peak_bucket(buckets: list[ProfileBucket]) -> int | None:
    """O bucket de maior total; em empate, o primeiro. None se não houve atividade."""
    busiest = max(buckets, key=lambda b: (b.total, -b.bucket), default=None)
    return busiest.bucket if busiest is not None and busiest.total > 0 else None
