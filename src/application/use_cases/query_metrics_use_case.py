from datetime import timedelta

from src.application.messaging.metric_payloads import event_metrics_payload, zone_metrics_payload
from src.application.parsers.envelope_parser import parse_utc_timestamp
from src.domain.exceptions import DomainError, MalformedEventEnvelopeError, QueryRejectedError
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
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

    Lê só métricas LIVE. As métricas por zona agregam todas as classes contadas pela zona
    (as classes que a zona conta vêm do artefato ZONES); por isso o filtro class é aceito
    em ZONE mas não restringe a série, e os itens saem sem o campo class.
    """

    def __init__(self, repository: ITimeSeriesRepository) -> None:
        self._repository = repository

    def execute(self, payload: dict) -> dict:
        metric = payload.get("metric")
        if metric not in ("ZONE", "EVENT"):
            raise QueryRejectedError(INVALID_QUERY, "metric deve ser ZONE ou EVENT.")
        granularity = payload.get("granularity")
        if granularity not in GRANULARITY_SECONDS:
            raise QueryRejectedError(
                INVALID_QUERY, f"granularity deve ser uma de {list(GRANULARITY_SECONDS)}."
            )
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
            if zone_id is not None and not self._repository.zone_exists(zone_id):
                raise QueryRejectedError(UNKNOWN_ZONE, f"Zona sem métricas no S5: {zone_id!r}.")
            series = [
                zone_metrics_payload(m, granularity)
                for m in self._repository.query_zone_series(period, granularity, zone_id)
            ]
        else:
            series = [
                event_metrics_payload(m, granularity)
                for m in self._repository.query_event_series(
                    period,
                    granularity,
                    event_type=payload.get("event_type"),
                    zone_id=zone_id,
                    object_class=payload.get("class"),
                )
            ]

        if len(series) > MAX_POINTS:
            raise QueryRejectedError(
                PERIOD_TOO_LONG,
                f"A série tem {len(series)} pontos, acima de {MAX_POINTS}; filtre por zona ou "
                "tipo de evento, ou reduza o período.",
            )
        return {"series": series}
