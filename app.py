"""Ponto de entrada da API REST do S5 (Métricas e Séries Temporais).

Uso: uvicorn app:app --reload
"""

import os

from fastapi import FastAPI

from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router

repository = DuckDBTimeSeriesRepository(os.getenv("S5_DATABASE_PATH", "s5_metrics.db"))

app = FastAPI(title="S5 — Métricas e Séries Temporais")
app.include_router(create_metrics_query_router(repository))
