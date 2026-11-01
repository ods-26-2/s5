import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import duckdb

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.entities.session_start import LIVE
from src.domain.services.presence_accumulator import PresenceKey
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.value_objects.time_window import TimeWindow


PRESENCE_BUCKET = timedelta(minutes=1)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DuckDBTimeSeriesRepository(ITimeSeriesRepository):
    """Armazenamento analítico colunar (OLAP) das métricas por zona, por tipo de evento e
    da presença por célula, com consultas SQL de séries temporais.

    Toda linha guarda stored_at, o instante UTC em que foi gravada. É por ele que os dados
    de replay expiram, já que o tempo de captura deles é o da gravação reproduzida.

    O repositório é usado por várias threads (leitura do Kafka, fechamento de janelas, API).
    Uma conexão DuckDB não é segura entre threads, então cada thread usa o próprio cursor,
    como a documentação do DuckDB recomenda; todos enxergam o mesmo banco.
    """

    def __init__(
        self, database_path: str = ":memory:", clock: Callable[[], datetime] = _utc_now
    ) -> None:
        self._root_connection = duckdb.connect(database_path)
        self._thread_local = threading.local()
        self._clock = clock
        self._create_schema()

    @property
    def _connection(self) -> duckdb.DuckDBPyConnection:
        cursor = getattr(self._thread_local, "cursor", None)
        if cursor is None:
            cursor = self._root_connection.cursor()
            self._thread_local.cursor = cursor
        return cursor

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS occupancy_metrics (
                zone_id VARCHAR,
                granularity VARCHAR,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                dwell_time_avg DOUBLE,
                occupancy_peak INTEGER,
                total_count INTEGER,
                occupancy_avg DOUBLE DEFAULT 0,
                mode VARCHAR DEFAULT 'LIVE',
                session_id VARCHAR,
                stored_at TIMESTAMP
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_metrics (
                event_type VARCHAR,
                zone_id VARCHAR,
                object_class VARCHAR,
                granularity VARCHAR,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                count INTEGER,
                uncertain_count INTEGER,
                duration_avg_ms INTEGER,
                mode VARCHAR DEFAULT 'LIVE',
                session_id VARCHAR,
                stored_at TIMESTAMP
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS presence_cells (
                mode VARCHAR,
                session_id VARCHAR,
                space_kind VARCHAR,
                space_key VARCHAR,
                object_class VARCHAR,
                cell_x INTEGER,
                cell_y INTEGER,
                bucket_start TIMESTAMP,
                seconds DOUBLE,
                stored_at TIMESTAMP
            )
            """
        )
        # Bancos criados antes destas colunas existirem as recebem sem perder dados; o que
        # já estava gravado veio da captura ao vivo.
        for statement in (
            "ALTER TABLE occupancy_metrics ADD COLUMN IF NOT EXISTS occupancy_avg DOUBLE DEFAULT 0",
            "ALTER TABLE occupancy_metrics ADD COLUMN IF NOT EXISTS mode VARCHAR DEFAULT 'LIVE'",
            "ALTER TABLE occupancy_metrics ADD COLUMN IF NOT EXISTS session_id VARCHAR",
            "ALTER TABLE event_metrics ADD COLUMN IF NOT EXISTS mode VARCHAR DEFAULT 'LIVE'",
            "ALTER TABLE event_metrics ADD COLUMN IF NOT EXISTS session_id VARCHAR",
            "ALTER TABLE occupancy_metrics ADD COLUMN IF NOT EXISTS stored_at TIMESTAMP",
            "ALTER TABLE event_metrics ADD COLUMN IF NOT EXISTS stored_at TIMESTAMP",
            "ALTER TABLE presence_cells ADD COLUMN IF NOT EXISTS stored_at TIMESTAMP",
        ):
            self._connection.execute(statement)
        # Linhas gravadas antes de stored_at existir recebem o instante da migração: assim
        # as de replay expiram replay_days depois dela, em vez de nunca expirarem.
        migrated_at = self._clock()
        for table in ("occupancy_metrics", "event_metrics", "presence_cells"):
            self._connection.execute(
                f"UPDATE {table} SET stored_at = ? WHERE stored_at IS NULL", [migrated_at]
            )

    def save_occupancy_metric(
        self,
        metric: OccupancyMetric,
        granularity: str,
        mode: str = LIVE,
        session_id: str | None = None,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO occupancy_metrics
                (zone_id, granularity, start_time, end_time, dwell_time_avg, occupancy_peak,
                 total_count, occupancy_avg, mode, session_id, stored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                metric.zone_id,
                granularity,
                metric.window.start_time,
                metric.window.end_time,
                metric.dwell_time_avg,
                metric.occupancy_peak,
                metric.total_count,
                metric.occupancy_avg,
                mode,
                session_id,
                self._clock(),
            ],
        )

    def save_event_metric(
        self,
        metric: EventMetric,
        granularity: str,
        mode: str = LIVE,
        session_id: str | None = None,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO event_metrics
                (event_type, zone_id, object_class, granularity, start_time, end_time,
                 count, uncertain_count, duration_avg_ms, mode, session_id, stored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                metric.event_type,
                metric.zone_id,
                metric.object_class,
                granularity,
                metric.window.start_time,
                metric.window.end_time,
                metric.count,
                metric.uncertain_count,
                metric.duration_avg_ms,
                mode,
                session_id,
                self._clock(),
            ],
        )

    def save_presence(self, cells: list[tuple[PresenceKey, float, str]]) -> None:
        stored_at = self._clock()
        rows = [
            [
                mode,
                key.session_id,
                key.space_kind,
                key.space_key,
                key.object_class,
                key.cell_x,
                key.cell_y,
                key.bucket_start,
                seconds,
                stored_at,
            ]
            for key, seconds, mode in cells
        ]
        if rows:
            self._connection.executemany(
                """
                INSERT INTO presence_cells
                    (mode, session_id, space_kind, space_key, object_class,
                     cell_x, cell_y, bucket_start, seconds, stored_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def query_presence(
        self,
        space_kind: str,
        space_key: str,
        window: TimeWindow,
        object_class: str | None = None,
        mode: str = LIVE,
    ) -> list[tuple[int, int, float]]:
        rows = self._connection.execute(
            """
            SELECT cell_x, cell_y, SUM(seconds)
            FROM presence_cells
            WHERE space_kind = ? AND space_key = ? AND mode = ?
                AND bucket_start >= ? AND bucket_start < ?
                AND (? IS NULL OR object_class = ?)
            GROUP BY cell_x, cell_y
            ORDER BY cell_y, cell_x
            """,
            [space_kind, space_key, mode, window.start_time, window.end_time, object_class, object_class],
        ).fetchall()
        return [(row[0], row[1], row[2]) for row in rows]

    def query_zone_series(
        self, window: TimeWindow, granularity: str, zone_id: str | None = None, mode: str = LIVE
    ) -> list[OccupancyMetric]:
        rows = self._connection.execute(
            """
            SELECT zone_id, start_time, end_time, dwell_time_avg, occupancy_peak, total_count, occupancy_avg
            FROM occupancy_metrics
            WHERE granularity = ? AND mode = ? AND start_time >= ? AND end_time <= ?
                AND (? IS NULL OR zone_id = ?)
            ORDER BY start_time, zone_id
            """,
            [granularity, mode, window.start_time, window.end_time, zone_id, zone_id],
        ).fetchall()
        return [
            OccupancyMetric(
                zone_id=row[0],
                window=TimeWindow(start_time=row[1], end_time=row[2]),
                dwell_time_avg=row[3],
                occupancy_peak=row[4],
                total_count=row[5],
                occupancy_avg=row[6],
            )
            for row in rows
        ]

    def query_event_series(
        self,
        window: TimeWindow,
        granularity: str,
        event_type: str | None = None,
        zone_id: str | None = None,
        object_class: str | None = None,
        mode: str = LIVE,
    ) -> list[EventMetric]:
        rows = self._connection.execute(
            """
            SELECT event_type, zone_id, object_class, start_time, end_time,
                   count, uncertain_count, duration_avg_ms
            FROM event_metrics
            WHERE granularity = ? AND mode = ? AND start_time >= ? AND end_time <= ?
                AND (? IS NULL OR event_type = ?)
                AND (? IS NULL OR zone_id = ?)
                AND (? IS NULL OR object_class = ?)
            ORDER BY start_time, event_type, zone_id, object_class
            """,
            [
                granularity, mode, window.start_time, window.end_time,
                event_type, event_type, zone_id, zone_id, object_class, object_class,
            ],
        ).fetchall()
        return [
            EventMetric(
                event_type=row[0],
                window=TimeWindow(start_time=row[3], end_time=row[4]),
                count=row[5],
                uncertain_count=row[6],
                zone_id=row[1],
                object_class=row[2],
                duration_avg_ms=row[7],
            )
            for row in rows
        ]

    def delete_live_metrics_before(self, granularity: str, cutoff: datetime) -> int:
        return sum(
            self._delete(
                f"DELETE FROM {table} WHERE mode = ? AND granularity = ? AND end_time < ?",
                [LIVE, granularity, cutoff],
            )
            for table in ("occupancy_metrics", "event_metrics")
        )

    def delete_live_presence_before(self, cutoff: datetime) -> int:
        return self._delete(
            "DELETE FROM presence_cells WHERE mode = ? AND bucket_start < ?",
            [LIVE, cutoff - PRESENCE_BUCKET],
        )

    def delete_replay_stored_before(self, cutoff: datetime) -> int:
        return sum(
            self._delete(f"DELETE FROM {table} WHERE mode <> ? AND stored_at < ?", [LIVE, cutoff])
            for table in ("occupancy_metrics", "event_metrics", "presence_cells")
        )

    def _delete(self, statement: str, parameters: list) -> int:
        return self._connection.execute(statement, parameters).fetchone()[0]

    def zone_exists(self, zone_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM occupancy_metrics WHERE zone_id = ? LIMIT 1", [zone_id]
        ).fetchone()
        return row is not None
