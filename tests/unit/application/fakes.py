from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.entities.session_start import LIVE
from src.domain.services.presence_accumulator import PresenceKey
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.value_objects.time_window import TimeWindow


class FakeTimeSeriesRepository(ITimeSeriesRepository):
    """Repositório em memória para testar casos de uso sem I/O real."""

    def __init__(self) -> None:
        self.saved_metrics: list[tuple[OccupancyMetric, str]] = []
        self.saved_modes: list[tuple[str, str | None]] = []
        self.saved_event_metrics: list[tuple[EventMetric, str]] = []
        self.saved_presence: list[tuple[PresenceKey, float, str]] = []
        self.purge_calls: list[tuple[str, str | None, object]] = []

    def save_occupancy_metric(
        self, metric: OccupancyMetric, granularity: str, mode: str = LIVE, session_id: str | None = None
    ) -> None:
        self.saved_metrics.append((metric, granularity))
        self.saved_modes.append((mode, session_id))

    def save_event_metric(
        self, metric: EventMetric, granularity: str, mode: str = LIVE, session_id: str | None = None
    ) -> None:
        self.saved_event_metrics.append((metric, granularity))

    def save_presence(self, cells: list[tuple[PresenceKey, float, str]]) -> None:
        self.saved_presence.extend(cells)

    def query_presence(self, space_kind, space_key, window, object_class=None, mode=LIVE):
        totals: dict[tuple[int, int], float] = {}
        for key, seconds, saved_mode in self.saved_presence:
            if (
                key.space_kind == space_kind
                and key.space_key == space_key
                and saved_mode == mode
                and window.start_time <= key.bucket_start < window.end_time
                and object_class in (None, key.object_class)
            ):
                cell = (key.cell_x, key.cell_y)
                totals[cell] = totals.get(cell, 0.0) + seconds
        return [(x, y, s) for (x, y), s in sorted(totals.items(), key=lambda i: (i[0][1], i[0][0]))]

    def query_zone_series(self, window, granularity, zone_id=None, mode=LIVE):
        return [
            metric
            for metric, saved_granularity in self.saved_metrics
            if saved_granularity == granularity and zone_id in (None, metric.zone_id)
        ]

    def query_event_series(
        self, window, granularity, event_type=None, zone_id=None, object_class=None, mode=LIVE
    ):
        return [
            metric
            for metric, saved_granularity in self.saved_event_metrics
            if saved_granularity == granularity and event_type in (None, metric.event_type)
        ]

    def delete_live_metrics_before(self, granularity, cutoff):
        self.purge_calls.append(("metrics", granularity, cutoff))
        return 0

    def delete_live_presence_before(self, cutoff):
        self.purge_calls.append(("presence", None, cutoff))
        return 0

    def delete_replay_stored_before(self, cutoff):
        self.purge_calls.append(("replay", None, cutoff))
        return 0

    def zone_exists(self, zone_id: str) -> bool:
        return any(metric.zone_id == zone_id for metric, _ in self.saved_metrics)
