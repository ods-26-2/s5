"""Teste curto do S5 em um broker Kafka: manda uma consulta e espera a reply.

Prova leitura e escrita sem publicar em tópicos que outros componentes consomem, porque só
o S5 atende ods.s5.metrics.query. Cria os dois tópicos da consulta se não existirem e termina
sozinho em no máximo 1 minuto e meio.

A consulta é reenviada a cada 15 s: o S5 começa em `latest` e leva até 30 s para descobrir um
tópico novo, então as primeiras podem ser enviadas antes de ele estar lendo.

Com o S5 rodando no mesmo broker:
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
REPLY_TIMEOUT_SECONDS = 75
RESEND_SECONDS = 15


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
            # earliest: a reply não se perde se o leitor entrar no grupo depois dela. Replies
            # antigas são ignoradas pelo correlation_id.
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    reader.subscribe([REPLY_TOPIC])
    producer = Producer({"bootstrap.servers": brokers})
    sent: dict[str, float] = {}
    started = time.monotonic()
    last_sent = None
    reply = None
    while reply is None and time.monotonic() - started < REPLY_TIMEOUT_SECONDS:
        if last_sent is None or time.monotonic() - last_sent >= RESEND_SECONDS:
            query = build_query()
            producer.produce(QUERY_TOPIC, value=json.dumps(query).encode("utf-8"))
            producer.flush(10)
            last_sent = time.monotonic()
            sent[query["message_id"]] = last_sent
        record = reader.poll(1.0)
        if record is None or record.error():
            continue
        message = json.loads(record.value())
        if message.get("correlation_id") in sent:
            reply = message
    reader.close()

    if reply is None:
        print(f"FALHOU: sem reply em {REPLY_TIMEOUT_SECONDS} s, com {len(sent)} consultas enviadas. O S5 está rodando neste broker?")
        return 1
    payload = reply["payload"]
    latency = time.monotonic() - sent[reply["correlation_id"]]
    print(f"OK: reply em {latency:.1f} s, {len(sent)}ª consulta, após {time.monotonic() - started:.0f} s; status {payload['status']}, schema {reply['schema']}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
