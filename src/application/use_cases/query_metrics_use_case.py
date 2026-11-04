from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.application.messaging.metric_payloads import event_metrics_payload, zone_metrics_payload
from src.application.parsers.envelope_parser import parse_utc_timestamp
from src.application.state.artifact_catalog import ArtifactCatalog
from src.domain.exceptions import DomainError, MalformedEventEnvelopeError, QueryRejectedError
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.activity_profile import (
    HOUR_OF_DAY,
    PROFILES,
    ProfileBucket,
    event_profile,
    peak_bucket,
    zone_profile,
)
from src.domain.value_objects.granularity import GRANULARITY_SECONDS
from src.domain.value_objects.time_window import TimeWindow

MAX_POINTS = 1000
INVALID_QUERY = "INVALID_QUERY"
PERIOD_TOO_LONG = "PERIOD_TOO_LONG"
UNKNOWN_ZONE = "UNKNOWN_ZONE"


def parse_period(payload: dict) -> TimeWindow:
    """Lê period_start_at/period_end_at de uma consulta; formato inválido vira INVALID_QUERY."""
    try:
        return TimeWindow(
            start_time=parse_utc_timestamp(payload["period_start_at"], "period_start_at"),
            end_time=parse_utc_timestamp(payload["period_end_at"], "period_end_at"),
        )
    except KeyError as error:
        raise QueryRejectedError(INVALID_QUERY, f"Campo obrigatório ausente: {error}.") from error
    except (MalformedEventEnvelopeError, DomainError) as error:
        raise QueryRejectedError(INVALID_QUERY, str(error)) from error


class QueryMetricsUseCase:
    """Atende ods.s5.metrics.query: a série histórica de métricas por zona (ZONE) ou por
    tipo de evento (EVENT), em ordem cronológica, com no máximo 1000 pontos.

    Com `profile` (HOUR_OF_DAY, DAY_OF_WEEK ou DAY_OF_MONTH), a reply traz também o perfil
    de atividade da série e o bucket de pico, no fuso `timezone` (IANA, padrão UTC). É o
    "horário de pico" das atividades de S5; HOUR_OF_DAY exige granularidade de até 1h.
    Esses dois campos são da versão 1.1 dos contratos de consulta, compatível com a 1.0.

    Lê só métricas LIVE. As métricas por zona agregam todas as classes contadas pela zona
    (as classes que a zona conta vêm do artefato ZONES); por isso o filtro class é aceito
    em ZONE mas não restringe a série, e os itens saem sem o campo class.
    """

    def __init__(self, repository: ITimeSeriesRepository, catalog: ArtifactCatalog | None = None) -> None:
        self._repository = repository
        self._catalog = catalog or ArtifactCatalog()

    def execute(self, payload: dict) -> dict:
        metric = payload.get("metric")
        if metric not in ("ZONE", "EVENT"):
            raise QueryRejectedError(INVALID_QUERY, "metric deve ser ZONE ou EVENT.")
        granularity = payload.get("granularity")
        if granularity not in GRANULARITY_SECONDS:
            raise QueryRejectedError(
                INVALID_QUERY, f"granularity deve ser uma de {list(GRANULARITY_SECONDS)}."
            )
        profile, zone = self._profile_request(payload, granularity)
        period = parse_period(payload)
        if period.duration_seconds / GRANULARITY_SECONDS[granularity] > MAX_POINTS:
            raise QueryRejectedError(
                PERIOD_TOO_LONG,
                f"O período tem mais de {MAX_POINTS} janelas de {granularity}; "
                "use uma granularidade maior ou um período menor.",
            )

        zone_id = payload.get("zone_id")
        if metric == "ZONE":
            if payload.get("event_type") is not None:
                raise QueryRejectedError(INVALID_QUERY, "event_type só vale em metric EVENT.")
            entries = self._catalog.zone_entries()
            if zone_id is not None and zone_id not in entries and not self._repository.zone_exists(zone_id):
                raise QueryRejectedError(
                    UNKNOWN_ZONE, f"Zona desconhecida: {zone_id!r} não está no artefato ZONES nem tem métricas no S5."
                )
            metrics = self._repository.query_zone_series(period, granularity, zone_id)
            series = [
                zone_metrics_payload(m, granularity, entries[m.zone_id].space_id if m.zone_id in entries else None)
                for m in metrics
            ]
            buckets = zone_profile(metrics, profile, zone) if profile else None
        else:
            metrics = self._repository.query_event_series(
                period,
                granularity,
                event_type=payload.get("event_type"),
                zone_id=zone_id,
                object_class=payload.get("class"),
            )
            series = [event_metrics_payload(m, granularity) for m in metrics]
            buckets = event_profile(metrics, profile, zone) if profile else None

        if len(series) > MAX_POINTS:
            raise QueryRejectedError(
                PERIOD_TOO_LONG,
                f"A série tem {len(series)} pontos, acima de {MAX_POINTS}; filtre por zona ou "
                "tipo de evento, ou reduza o período.",
            )
        if buckets is None:
            return {"series": series}
        return {
            "series": series,
            "profile": {
                "by": profile,
                "timezone": payload.get("timezone", "UTC"),
                "peak_bucket": peak_bucket(buckets),
                "buckets": [_bucket_payload(bucket, metric) for bucket in buckets],
            },
        }

    @staticmethod
    def _profile_request(payload: dict, granularity: str) -> tuple[str | None, ZoneInfo | None]:
        profile = payload.get("profile")
        if profile is None:
            return None, None
        if profile not in PROFILES:
            raise QueryRejectedError(INVALID_QUERY, f"profile deve ser um de {list(PROFILES)}.")
        if profile == HOUR_OF_DAY and GRANULARITY_SECONDS[granularity] > 3600:
            raise QueryRejectedError(INVALID_QUERY, "HOUR_OF_DAY exige granularity de até 1h.")
        name = payload.get("timezone", "UTC")
        try:
            return profile, ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
            raise QueryRejectedError(INVALID_QUERY, f"timezone desconhecido: {name!r}.") from error


def _bucket_payload(bucket: ProfileBucket, metric: str) -> dict:
    if metric == "ZONE":
        return {
            "bucket": bucket.bucket,
            "windows": bucket.windows,
            "total_count": bucket.total,
            "occupancy_peak": bucket.occupancy_peak,
            "occupancy_avg": round(bucket.occupancy_avg, 4),
        }
    return {
        "bucket": bucket.bucket,
        "windows": bucket.windows,
        "count": bucket.total,
        "uncertain_count": bucket.uncertain,
    }
