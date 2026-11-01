"""Teste curto do S5 em um broker Kafka: manda uma consulta e espera a reply.

Prova leitura e escrita sem publicar em tópicos que outros componentes consomem, porque só
o S5 atende ods.s5.metrics.query. Cria os dois tópicos da consulta se não existirem e termina
sozinho em no máximo 1 minuto.

Com o S5 rodando no mesmo broker há pelo menos 15 s (ele começa em `latest`):
    python scripts/smoke_kafka_query.py <host:porta>
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

QUERY_TOPIC = "ods.s5.metrics.query"
REPLY_TOPIC = "ods.s5.metrics.reply"
REPLY_TIMEOUT_SECONDS = 45
READER_WARMUP_POLLS = 10


def create_topics(brokers: str) -> None:
    admin = AdminClient({"bootstrap.servers": brokers})
    topics = [NewTopic(name, num_partitions=1, replication_factor=1) for name in (QUERY_TOPIC, REPLY_TOPIC)]
    for name, future in admin.create_topics(topics).items():
        try:
            future.result(15)
            print(f"tópico criado: {name}")
        except Exception as error:
            if "already exists" not in str(error).lower():
                raise


def build_query() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "message_type": "query",
        "message_id": str(uuid.uuid4()),
        "schema": QUERY_TOPIC,
        "schema_version": "1.0",
        "producer": "B4",
        "target": "S5",
        "published_at": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "payload": {
            "metric": "EVENT",
            "period_start_at": now.strftime("%Y-%m-%dT00:00:00.000Z"),
            "period_end_at": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "granularity": "1h",
        },
    }


def main(brokers: str) -> int:
    create_topics(brokers)
    reader = Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": f"S5-smoke-{uuid.uuid4()}",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )
    reader.subscribe([REPLY_TOPIC])
    for _ in range(READER_WARMUP_POLLS):
        reader.poll(1.0)

    query = build_query()
    started = time.monotonic()
    producer = Producer({"bootstrap.servers": brokers})
    producer.produce(QUERY_TOPIC, value=json.dumps(query).encode("utf-8"))
    producer.flush(10)

    reply = None
    while reply is None and time.monotonic() - started < REPLY_TIMEOUT_SECONDS:
        record = reader.poll(1.0)
        if record is None or record.error():
            continue
        message = json.loads(record.value())
        if message.get("correlation_id") == query["message_id"]:
            reply = message
    reader.close()

    if reply is None:
        print(f"FALHOU: sem reply em {REPLY_TIMEOUT_SECONDS} s. O S5 está rodando neste broker há 15 s?")
        return 1
    payload = reply["payload"]
    print(f"OK: reply em {time.monotonic() - started:.1f} s, status {payload['status']}, schema {reply['schema']}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
