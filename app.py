"""Ponto de entrada do S5 (Métricas e Séries Temporais).

Sobe o serviço completo: assina os tópicos de entrada e de
consulta, fecha as janelas a cada S5_TICK_SECONDS, apaga o que passou do prazo de
retenção a cada S5_PURGE_SECONDS e expõe a API REST de depuração.

Com S5_KAFKA_BROKERS definido, o barramento é o Kafka nesse endereço. Sem ele, é o barramento
em memória, e mensagens só chegam de dentro do processo. Outras variáveis: S5_KAFKA_GROUP_ID
e S5_KAFKA_OFFSET_RESET.

Artefatos fixados na build: S5_ARTIFACTS lista, separados por vírgula, os arquivos com o
descritor comum (seção 8) de cada ZONES e CALIBRATION. S5_ARTIFACT_REGISTRY_DIR é o diretório
para URIs registry://, enquanto o registro de B5 não tem formato definido.

Uso: uvicorn app:app --reload
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI

from src.composition import build_s5
from src.infrastructure.artifacts.file_artifact_source import FileArtifactSource, read_descriptor_files
from src.infrastructure.b3_bus.b3_event_consumer import InMemoryB3EventConsumer
from src.infrastructure.b3_bus.kafka_b3_bus import DEFAULT_GROUP_ID, DEFAULT_OFFSET_RESET, KafkaB3Bus
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
logger = logging.getLogger("s5")

repository = DuckDBTimeSeriesRepository(os.getenv("S5_DATABASE_PATH", "s5_metrics.db"))
kafka_brokers = os.getenv("S5_KAFKA_BROKERS", "").strip()
bus = (
    KafkaB3Bus(
        kafka_brokers,
        group_id=os.getenv("S5_KAFKA_GROUP_ID", DEFAULT_GROUP_ID),
        auto_offset_reset=os.getenv("S5_KAFKA_OFFSET_RESET", DEFAULT_OFFSET_RESET),
    )
    if kafka_brokers
    else InMemoryB3EventConsumer()
)
registry_dir = os.getenv("S5_ARTIFACT_REGISTRY_DIR", "").strip()
artifact_files = [Path(p.strip()) for p in os.getenv("S5_ARTIFACTS", "").split(",") if p.strip()]
service = build_s5(
    bus,
    bus,
    repository,
    artifact_source=FileArtifactSource(Path(registry_dir) if registry_dir else None),
    initial_artifacts=read_descriptor_files(artifact_files),
)
logger.info("Artefatos carregados na partida: %s", service.catalog.versions() or "nenhum")
tick_seconds = float(os.getenv("S5_TICK_SECONDS", "5"))
purge_seconds = float(os.getenv("S5_PURGE_SECONDS", "3600"))


def _purge_expired() -> None:
    removed = service.purge.execute(datetime.now(timezone.utc).replace(tzinfo=None))
    logger.info("Expurgo de retenção: %s", removed)


async def _run_periodically(task, interval_seconds: float, failure_message: str) -> None:
    while True:
        try:
            # Em outra thread: o evento de loop continua atendendo a API durante o disparo.
            await asyncio.to_thread(task)
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
app.include_router(create_metrics_query_router(repository, service.catalog))
