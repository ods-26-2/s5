"""Ponto de entrada do S5 (Métricas e Séries Temporais).

Sobe o serviço completo sobre o barramento em memória: assina os tópicos de entrada e de
consulta, fecha as janelas a cada S5_TICK_SECONDS e expõe a API REST de depuração.
Enquanto não houver cliente de broker real, mensagens só chegam de dentro do processo.

Uso: uvicorn app:app --reload
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.composition import build_s5
from src.infrastructure.b3_bus.b3_event_consumer import InMemoryB3EventConsumer
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router

logger = logging.getLogger("s5")

repository = DuckDBTimeSeriesRepository(os.getenv("S5_DATABASE_PATH", "s5_metrics.db"))
bus = InMemoryB3EventConsumer()
service = build_s5(bus, bus, repository)
tick_seconds = float(os.getenv("S5_TICK_SECONDS", "5"))


async def _close_windows_periodically() -> None:
    while True:
        try:
            service.worker.run()
        except Exception:  # um disparo com erro não pode parar os seguintes
            logger.exception("Falha ao fechar janelas de métricas.")
        await asyncio.sleep(tick_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bus.start()
    task = asyncio.create_task(_close_windows_periodically())
    yield
    task.cancel()
    bus.stop()


app = FastAPI(title="S5 — Métricas e Séries Temporais", lifespan=lifespan)
app.include_router(create_metrics_query_router(repository))
