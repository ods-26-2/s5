"""S5 completo contra um broker Kafka real. Só roda com S5_TEST_KAFKA_BROKERS definido, e deve
apontar para um broker local descartável (ver README): este teste cria tópicos e publica
mensagens, e o broker do projeto é pago e compartilhado.

    docker run -d --rm --name s5-kafka-teste -p 9092:9092 apache/kafka:3.9.0
    S5_TEST_KAFKA_BROKERS=localhost:9092 pytest tests/integration/test_kafka_b3_bus_real.py
"""

import json
import os
import time
import uuid
from datetime import datetime

import pytest
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.composition import build_s5
from src.infrastructure.b3_bus.kafka_b3_bus import KafkaB3Bus
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from tests.fixtures.spec_examples import metrics_query, qualified_event, zone_occupancy, zone_transition_exit

BROKERS = os.getenv("S5_TEST_KAFKA_BROKERS")
pytestmark = pytest.mark.skipif(not BROKERS, reason="S5_TEST_KAFKA_BROKERS não definido")

TIMEOUT_SECONDS = 60
OUTPUT_TOPICS = ["ods.s5.zone_metrics", "ods.s5.event_metrics", "ods.s5.metrics.reply", "ods.s5.heatmap.reply"]


def _fail(message, error):
    raise error


def _create_topics(topics):
    admin = AdminClient({"bootstrap.servers": BROKERS})
    futures = admin.create_topics([NewTopic(t, num_partitions=1, replication_factor=1) for t in topics])
    for future in futures.values():
        try:
            future.result(10)
        except Exception as error:
            if "already exists" not in str(error).lower():
                raise


def _wait_for(condition, what):
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.2)
    pytest.fail(f"Tempo esgotado esperando {what}.")


def test_s5_le_publica_e_responde_por_um_kafka_real():
    bus = KafkaB3Bus(BROKERS, group_id=f"S5-teste-{uuid.uuid4()}", auto_offset_reset="earliest")
    clock_at = datetime(2026, 9, 23, 14, 30, 3)
    service = build_s5(
        bus,
        bus,
        DuckDBTimeSeriesRepository(":memory:"),
        clock=lambda: clock_at,
        granularities=("1m",),
        on_contract_violation=_fail,
    )
    _create_topics(
        [*bus._handlers, *OUTPUT_TOPICS]
    )
    reader = Consumer(
        {"bootstrap.servers": BROKERS, "group.id": f"teste-{uuid.uuid4()}", "auto.offset.reset": "earliest"}
    )
    reader.subscribe(OUTPUT_TOPICS)
    outside = Producer({"bootstrap.servers": BROKERS})
    bus.start()
    try:
        for topic, message in (
            ("ods.s1.zone_transition", zone_transition_exit()),
            ("ods.s1.zone_occupancy", zone_occupancy()),
            ("ods.s2.event", qualified_event()),
            ("ods.s1.zone_occupancy", b"isto nao e json"),
        ):
            value = message if isinstance(message, bytes) else json.dumps(message).encode("utf-8")
            outside.produce(topic, value=value)
        outside.flush(10)

        _wait_for(
            lambda: service.buffer.transitions and service.buffer.samples and service.buffer.events,
            "o S5 receber as mensagens do Kafka",
        )
        service.worker.run()

        query = metrics_query()
        query["message_id"] = str(uuid.uuid4())
        query["payload"].update(
            period_start_at="2026-09-23T14:00:00.000Z",
            period_end_at="2026-09-23T15:00:00.000Z",
            granularity="1m",
        )
        outside.produce("ods.s5.metrics.query", value=json.dumps(query).encode("utf-8"))
        outside.flush(10)

        received = {}

        def read_all_expected():
            record = reader.poll(1.0)
            if record is not None and not record.error():
                message = json.loads(record.value())
                if message["schema"] != "ods.s5.metrics.reply" or message["correlation_id"] == query["message_id"]:
                    received[record.topic()] = message
            return {"ods.s5.zone_metrics", "ods.s5.metrics.reply"} <= received.keys()

        _wait_for(read_all_expected, "as mensagens do S5 no Kafka")
    finally:
        bus.stop()
        reader.close()

    assert received["ods.s5.zone_metrics"]["payload"]["dwell_avg_s"] == 8395
    assert received["ods.s5.zone_metrics"]["producer"] == "S5"
    reply = received["ods.s5.metrics.reply"]
    assert reply["payload"]["status"] == "OK"
    assert [item["dwell_avg_s"] for item in reply["payload"]["series"]] == [8395]
