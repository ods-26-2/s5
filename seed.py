"""Popula o banco DuckDB do S5 com dados de exemplo para testar a API manualmente.

Uso: python seed.py  (respeita S5_DATABASE_PATH, como o app.py)
"""

import os
from datetime import datetime

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.value_objects.time_window import TimeWindow
from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository

repository = DuckDBTimeSeriesRepository(os.getenv("S5_DATABASE_PATH", "s5_metrics.db"))

repository.save_occupancy_metric(
    OccupancyMetric(
        zone_id="zona-1",
        window=TimeWindow(datetime(2026, 10, 9, 14, 0), datetime(2026, 10, 9, 14, 1)),
        dwell_time_avg=42.5,
        occupancy_peak=7,
        total_count=12,
    ),
    granularity="1m",
)

repository.save_heatmap_grid(
    HeatmapGrid(
        grid_id="grid-1",
        cells=(
            SpatialCell(WorldCoordinate(1.0, 2.0), 1.0),
            SpatialCell(WorldCoordinate(3.0, 4.0), 0.5),
        ),
    ),
    timestamp=datetime(2026, 10, 9, 14, 0),
)

print("Dados de exemplo gravados: zona-1 (métricas 1m) e grid-1 (mapa de calor) em 2026-10-09.")
