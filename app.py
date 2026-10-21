"""Ponto de entrada do S5 (Métricas e Séries Temporais).

Sobe o serviço completo sobre o barramento em memória: assina os tópicos de entrada e de
consulta, fecha as janelas a cada S5_TICK_SECONDS, apaga o que passou do prazo de
retenção a cada S5_PURGE_SECONDS e expõe a API REST de depuração.
Enquanto não houver cliente de broker real, mensagens só chegam de dentro do processo.

Uso: uvicorn app:app --reload
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from src.composition import build_s5
from src.infrastructure.b3_bus.b3_event_consumer import InMemoryB3EventConsumer
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
logger = logging.getLogger("s5")

repository = DuckDBTimeSeriesRepository(os.getenv("S5_DATABASE_PATH", "s5_metrics.db"))
bus = InMemoryB3EventConsumer()
service = build_s5(bus, bus, repository)
tick_seconds = float(os.getenv("S5_TICK_SECONDS", "5"))
purge_seconds = float(os.getenv("S5_PURGE_SECONDS", "3600"))


def _purge_expired() -> None:
    removed = service.purge.execute(datetime.now(timezone.utc).replace(tzinfo=None))
    logger.info("Expurgo de retenção: %s", removed)


async def _run_periodically(task, interval_seconds: float, failure_message: str) -> None:
    while True:
        try:
            task()
        except Exception:  # um disparo com erro não pode parar os seguintes
            logger.exception(failure_message)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bus.start()
    tasks = [
        asyncio.create_task(
            _run_periodically(service.worker.run, tick_seconds, "Falha ao fechar janelas de métricas.")
        ),
        asyncio.create_task(
            _run_periodically(_purge_expired, purge_seconds, "Falha no expurgo de retenção.")
        ),
    ]
    yield
    for task in tasks:
        task.cancel()
    bus.stop()


app = FastAPI(title="S5 — Métricas e Séries Temporais", lifespan=lifespan)
app.include_router(create_metrics_query_router(repository))
