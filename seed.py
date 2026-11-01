"""Popula o banco DuckDB do S5 com dados de exemplo para testar a API de depuração.

Uso: python seed.py  (respeita S5_DATABASE_PATH, como o app.py)
"""

import os
from datetime import datetime, timedelta

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.services.presence_accumulator import METERS, PresenceKey
from src.domain.value_objects.time_window import TimeWindow
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository

repository = DuckDBTimeSeriesRepository(os.getenv("S5_DATABASE_PATH", "s5_metrics.db"))
start = datetime(2026, 10, 9, 14, 0)

for quarter in range(4):
    window = TimeWindow(start + timedelta(minutes=15 * quarter), start + timedelta(minutes=15 * (quarter + 1)))
    repository.save_occupancy_metric(
        OccupancyMetric(
            zone_id="vaga-12", window=window, dwell_time_avg=1830.0,
            occupancy_peak=1, total_count=3, occupancy_avg=0.72,
        ),
        granularity="15m",
        session_id="seed",
    )

repository.save_event_metric(
    EventMetric(
        event_type="PPE_NON_COMPLIANT", window=TimeWindow(start, start + timedelta(hours=1)),
        count=4, uncertain_count=1, zone_id="galpao-solda", object_class="person", duration_avg_ms=12400,
    ),
    granularity="1h",
    session_id="seed",
)

repository.save_presence(
    [
        (PresenceKey("seed", METERS, "patio-1", "person", x, y, start + timedelta(minutes=10)), seconds, "LIVE")
        for x, y, seconds in ((34, 71, 42.0), (35, 71, 18.5), (40, 75, 7.0))
    ]
)

print("Dados de exemplo gravados em 2026-10-09, 14h–15h UTC:")
print("  vaga-12 (métricas de 15m), PPE_NON_COMPLIANT (1h) e presença em patio-1.")
