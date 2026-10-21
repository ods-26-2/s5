from datetime import datetime

import duckdb

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.entities.session_start import LIVE
from src.domain.services.presence_accumulator import PresenceKey
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.value_objects.time_window import TimeWindow
from src.domain.value_objects.world_coordinate import WorldCoordinate


class DuckDBTimeSeriesRepository(ITimeSeriesRepository):
    """Armazenamento analítico colunar (OLAP) de métricas de ocupação e células de mapa
    de calor, com consultas SQL de séries temporais para a aplicação."""

    def __init__(self, database_path: str = ":memory:") -> None:
        self._connection = duckdb.connect(database_path)
        self._create_schema()

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
                session_id VARCHAR
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
                session_id VARCHAR
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
                seconds DOUBLE
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS heatmap_cells (
                grid_id VARCHAR,
                timestamp TIMESTAMP,
                x DOUBLE,
                y DOUBLE,
                density DOUBLE
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
        ):
            self._connection.execute(statement)

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
                 total_count, occupancy_avg, mode, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                 count, uncertain_count, duration_avg_ms, mode, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ],
        )

    def query_event_metrics(
        self, event_type: str, window: TimeWindow, granularity: str, mode: str = LIVE
    ) -> list[EventMetric]:
        rows = self._connection.execute(
            """
            SELECT zone_id, object_class, start_time, end_time, count, uncertain_count, duration_avg_ms
            FROM event_metrics
            WHERE event_type = ? AND granularity = ? AND mode = ?
                AND start_time >= ? AND end_time <= ?
            ORDER BY start_time
            """,
            [event_type, granularity, mode, window.start_time, window.end_time],
        ).fetchall()

        return [
            EventMetric(
                event_type=event_type,
                window=TimeWindow(start_time=row[2], end_time=row[3]),
                count=row[4],
                uncertain_count=row[5],
                zone_id=row[0],
                object_class=row[1],
                duration_avg_ms=row[6],
            )
            for row in rows
        ]

    def save_presence(self, cells: list[tuple[PresenceKey, float, str]]) -> None:
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
            ]
            for key, seconds, mode in cells
        ]
        if rows:
            self._connection.executemany(
                "INSERT INTO presence_cells VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
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

    def zone_exists(self, zone_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM occupancy_metrics WHERE zone_id = ? LIMIT 1", [zone_id]
        ).fetchone()
        return row is not None

    def save_heatmap_grid(self, grid: HeatmapGrid, timestamp: datetime) -> None:
        rows = [
            [grid.grid_id, timestamp, cell.position.x, cell.position.y, cell.density]
            for cell in grid.cells
        ]
        if rows:
            self._connection.executemany(
                "INSERT INTO heatmap_cells (grid_id, timestamp, x, y, density) VALUES (?, ?, ?, ?, ?)",
                rows,
            )

    def query_metrics(
        self, zone_id: str, window: TimeWindow, granularity: str, mode: str = LIVE
    ) -> list[OccupancyMetric]:
        rows = self._connection.execute(
            """
            SELECT start_time, end_time, dwell_time_avg, occupancy_peak, total_count, occupancy_avg
            FROM occupancy_metrics
            WHERE zone_id = ? AND granularity = ? AND mode = ?
                AND start_time >= ? AND end_time <= ?
            ORDER BY start_time
            """,
            [zone_id, granularity, mode, window.start_time, window.end_time],
        ).fetchall()

        return [
            OccupancyMetric(
                zone_id=zone_id,
                window=TimeWindow(start_time=row[0], end_time=row[1]),
                dwell_time_avg=row[2],
                occupancy_peak=row[3],
                total_count=row[4],
                occupancy_avg=row[5],
            )
            for row in rows
        ]

    def query_heatmap(self, grid_id: str, window: TimeWindow) -> list[HeatmapGrid]:
        rows = self._connection.execute(
            """
            SELECT timestamp, x, y, density
            FROM heatmap_cells
            WHERE grid_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
            """,
            [grid_id, window.start_time, window.end_time],
        ).fetchall()

        grids_by_timestamp: dict[datetime, list[SpatialCell]] = {}
        for timestamp, x, y, density in rows:
            grids_by_timestamp.setdefault(timestamp, []).append(
                SpatialCell(position=WorldCoordinate(x=x, y=y), density=density)
            )

        return [
            HeatmapGrid(grid_id=grid_id, cells=tuple(cells)) for cells in grids_by_timestamp.values()
        ]
