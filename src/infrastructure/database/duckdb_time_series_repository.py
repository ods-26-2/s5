from datetime import datetime

import duckdb

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
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
                total_count INTEGER
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

    def save_occupancy_metric(self, metric: OccupancyMetric, granularity: str) -> None:
        self._connection.execute(
            """
            INSERT INTO occupancy_metrics
                (zone_id, granularity, start_time, end_time, dwell_time_avg, occupancy_peak, total_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                metric.zone_id,
                granularity,
                metric.window.start_time,
                metric.window.end_time,
                metric.dwell_time_avg,
                metric.occupancy_peak,
                metric.total_count,
            ],
        )

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
        self, zone_id: str, window: TimeWindow, granularity: str
    ) -> list[OccupancyMetric]:
        rows = self._connection.execute(
            """
            SELECT start_time, end_time, dwell_time_avg, occupancy_peak, total_count
            FROM occupancy_metrics
            WHERE zone_id = ? AND granularity = ? AND start_time >= ? AND end_time <= ?
            ORDER BY start_time
            """,
            [zone_id, granularity, window.start_time, window.end_time],
        ).fetchall()

        return [
            OccupancyMetric(
                zone_id=zone_id,
                window=TimeWindow(start_time=row[0], end_time=row[1]),
                dwell_time_avg=row[2],
                occupancy_peak=row[3],
                total_count=row[4],
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
