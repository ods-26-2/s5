from src.application.messaging.outgoing_envelope_factory import format_utc
from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.time_window import TimeWindow


def _window_fields(window: TimeWindow, granularity: str) -> dict:
    return {
        "window_start_at": format_utc(window.start_time),
        "window_end_at": format_utc(window.end_time),
        "granularity": granularity,
    }


def zone_metrics_payload(metric: OccupancyMetric, granularity: str) -> dict:
    """Payload de ods.s5.zone_metrics; é também o item da série de ods.s5.metrics.query."""
    return {
        "zone_id": metric.zone_id,
        **_window_fields(metric.window, granularity),
        "total_count": metric.total_count,
        "occupancy_peak": metric.occupancy_peak,
        "occupancy_avg": round(metric.occupancy_avg, 4),
        "dwell_avg_s": round(metric.dwell_time_avg),
    }


def event_metrics_payload(metric: EventMetric, granularity: str) -> dict:
    """Payload de ods.s5.event_metrics; é também o item da série de ods.s5.metrics.query."""
    payload = {"event_type": metric.event_type}
    if metric.zone_id is not None:
        payload["zone_id"] = metric.zone_id
    if metric.object_class is not None:
        payload["class"] = metric.object_class
    payload.update(_window_fields(metric.window, granularity))
    payload["count"] = metric.count
    payload["uncertain_count"] = metric.uncertain_count
    if metric.duration_avg_ms is not None:
        payload["duration_avg_ms"] = metric.duration_avg_ms
    return payload
