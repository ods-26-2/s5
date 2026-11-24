"""Demonstração do S5: publica mensagens de exemplo do S1 e do S2 e mostra o que o S5 responde.

Roda contra um Kafka local (ver scripts/demo_local.sh, que sobe tudo). Nunca aponte para o
broker do projeto: o script cria tópicos e publica uma sessão inteira de dados de exemplo.

    python scripts/demo_publish.py topicos <host:porta>   # cria os tópicos usados pelo S5
    python scripts/demo_publish.py executar <host:porta>  # publica, espera a janela e consulta
"""

import json
import math
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

TOPICS = [
    "ods.session.started",
    "ods.p6.replay.state",
    "ods.s1.zone_transition",
    "ods.s1.zone_occupancy",
    "ods.s1.position",
    "ods.s2.event",
    "ods.s2.entity",
    "ods.artifact.published",
    "ods.i3.calibration",
    "ods.s5.metrics.query",
    "ods.s5.heatmap.query",
    "ods.s5.zone_metrics",
    "ods.s5.event_metrics",
    "ods.s5.metrics.reply",
    "ods.s5.heatmap.reply",
]
OUTPUT_TOPICS = ["ods.s5.zone_metrics", "ods.s5.event_metrics", "ods.s5.metrics.reply", "ods.s5.heatmap.reply"]
GRACE_SECONDS = 4
REPLY_TIMEOUT_SECONDS = 30


def iso(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%dT%H:%M:%S.") + f"{instant.microsecond // 1000:03d}Z"


def create_topics(brokers: str) -> None:
    admin = AdminClient({"bootstrap.servers": brokers})
    for name, future in admin.create_topics([NewTopic(t, num_partitions=1, replication_factor=1) for t in TOPICS]).items():
        try:
            future.result(15)
        except Exception as error:
            if "already exists" not in str(error).lower():
                raise
    print(f"{len(TOPICS)} tópicos prontos.")


class Session:
    """Monta mensagens com o envelope comum (Especificação 1.0, seção 3) para uma sessão."""

    def __init__(self, started_at: datetime) -> None:
        self.session_id = str(uuid.uuid4())
        self.started_at = started_at
        self._sequence: dict[str, int] = {}

    def message(self, schema: str, producer: str, captured_at: datetime, payload: dict, **context) -> dict:
        sequence = self._sequence.get(producer, 0)
        self._sequence[producer] = sequence + 1
        return {
            "message_type": "event",
            "message_id": str(uuid.uuid4()),
            "schema": schema,
            "schema_version": "1.0",
            "producer": producer,
            "published_at": iso(datetime.now(timezone.utc)),
            "captured_at": iso(captured_at),
            "session_id": self.session_id,
            "sequence": sequence,
            **context,
            "payload": payload,
        }


def build_scenario(session: Session) -> list[tuple[str, dict]]:
    """Um pátio de estacionamento (artefato zones-a8-2): um carro passa 23 s na vaga 12, outro
    entra na vaga 13, uma pessoa atravessa o pátio a pé e o S2 qualifica um evento."""
    t0 = session.started_at
    s1 = {"source_id": "cam0", "artifact_version": "zones-a8-2"}
    at = lambda seconds: t0 + timedelta(seconds=seconds)  # noqa: E731
    messages = [
        ("ods.session.started", session.message(
            "ods.session.started", "P4", t0,
            {"mode": "LIVE", "started_at": iso(t0), "sources": ["cam0", "cam1"], "reason": "START"},
            source_id="cam0",
        )),
    ]

    def transition(seconds, zone_id, track_id, kind, dwell_s=None):
        payload = {"track_id": track_id, "class": "vehicle", "zone_id": zone_id, "transition": kind,
                   "entered_at": iso(at(seconds - (dwell_s or 0)))}
        if dwell_s is not None:
            payload["dwell_s"] = dwell_s
        return ("ods.s1.zone_transition", session.message("ods.s1.zone_transition", "S1", at(seconds), payload, **s1))

    def occupancy(seconds, zone_id, count, tracks):
        payload = {"zone_id": zone_id, "count": count, "count_by_class": {"vehicle": count},
                   "max_occupancy": 1, "track_ids": tracks}
        return ("ods.s1.zone_occupancy", session.message("ods.s1.zone_occupancy", "S1", at(seconds), payload, **s1))

    messages += [
        transition(2, "vaga-12", "t-carro-1", "ENTER"),
        occupancy(2, "vaga-12", 1, ["t-carro-1"]),
        transition(5, "vaga-13", "t-carro-2", "ENTER"),
        occupancy(5, "vaga-13", 1, ["t-carro-2"]),
        transition(25, "vaga-12", "t-carro-1", "EXIT", dwell_s=23),
        occupancy(25, "vaga-12", 0, []),
    ]

    # Uma pessoa atravessa o pátio a 0,5 m/s, uma posição a cada 0,5 s (de x = 3,0 a 6,0 m).
    for step in range(25):
        x = 3.0 + step * 0.125
        payload = {"frame_index": step * 15, "positions": [{
            "track_id": "t-pessoa-1", "class": "person", "point_px": [500 + step * 20, 700],
            "position_m": [round(x, 3), 7.1], "space_id": "patio-1", "zone_ids": [],
        }]}
        messages.append(("ods.s1.position", session.message("ods.s1.position", "S1", at(step * 0.5), payload, **s1)))

    messages.append(("ods.s2.event", session.message(
        "ods.s2.event", "S2", at(10),
        {"event_id": str(uuid.uuid4()), "event_type": "DWELL_EXCEEDED", "rule_id": "a8-permanencia-vaga",
         "status": "CONFIRMED", "phase": "STARTED", "confidence": 0.9, "class": "vehicle",
         "zone_id": "vaga-13", "started_at": iso(at(10)), "duration_ms": 0, "source_ids": ["cam0"],
         "details": {"dwell_s": 5}},
        source_id="cam0", artifact_version="rules-a8-1",
    )))
    return messages


def query(schema: str, payload: dict) -> dict:
    return {
        "message_type": "query",
        "message_id": str(uuid.uuid4()),
        "schema": schema,
        "schema_version": "1.1" if "profile" in payload else "1.0",
        "producer": "A8",
        "target": "S5",
        "published_at": iso(datetime.now(timezone.utc)),
        "payload": payload,
    }


def show(title: str, payload: dict) -> None:
    print(f"\n  {title}")
    print("  " + json.dumps(payload, ensure_ascii=False, indent=2).replace("\n", "\n  "))


def run(brokers: str) -> int:
    now = datetime.now(timezone.utc)
    session = Session(started_at=now - timedelta(seconds=30))
    reader = Consumer({"bootstrap.servers": brokers, "group.id": f"demo-{uuid.uuid4()}",
                       "auto.offset.reset": "earliest", "enable.auto.commit": False})
    reader.subscribe(OUTPUT_TOPICS)
    producer = Producer({"bootstrap.servers": brokers})

    scenario = build_scenario(session)
    for topic, message in scenario:
        producer.produce(topic, value=json.dumps(message).encode("utf-8"))
    producer.flush(10)
    counts = {}
    for topic, _ in scenario:
        counts[topic] = counts.get(topic, 0) + 1
    print(f"\n1. Publicadas {len(scenario)} mensagens da sessão {session.session_id[:8]}…")
    for topic, count in counts.items():
        print(f"     {count:3d} em {topic}")

    last_captured = max(datetime.fromisoformat(m["captured_at"]) for _, m in scenario)
    window_end = last_captured.replace(second=0, microsecond=0) + timedelta(minutes=1)
    wait_until = window_end + timedelta(seconds=GRACE_SECONDS)
    print(f"\n2. O S5 fecha a janela de 1 minuto que termina às {window_end:%H:%M:%S} UTC.")

    metrics = []
    while datetime.now(timezone.utc) < wait_until + timedelta(seconds=10):
        remaining = math.ceil((wait_until - datetime.now(timezone.utc)).total_seconds())
        if remaining > 0:
            print(f"\r   Aguardando… {remaining:3d} s", end="", flush=True)
        record = reader.poll(1.0)
        if record is None or record.error():
            continue
        message = json.loads(record.value())
        if message.get("session_id") == session.session_id and record.topic() in OUTPUT_TOPICS[:2]:
            metrics.append(message)
        if metrics and datetime.now(timezone.utc) > wait_until:
            break
    print()

    if not metrics:
        print("   Nenhuma métrica chegou. O S5 está rodando neste broker? (ver scripts/demo_local.sh)")
        reader.close()
        return 1
    for message in sorted(metrics, key=lambda m: (m["schema"], m["payload"].get("zone_id", ""))):
        show(f"{message['schema']} ({message['payload']['granularity']})", message["payload"])

    # Última hora até a janela fechada: em 1m são 61 janelas, abaixo do limite de 1000 do S5.
    period = {"period_start_at": iso(window_end - timedelta(hours=1)), "period_end_at": iso(window_end)}
    queries = [
        ("3. Série da vaga 12 com horário de pico em São Paulo", query("ods.s5.metrics.query", {
            "metric": "ZONE", "zone_id": "vaga-12", "granularity": "1m",
            "profile": "HOUR_OF_DAY", "timezone": "America/Sao_Paulo", **period})),
        ("4. Mapa de calor do pátio (células de 0,5 m)", query("ods.s5.heatmap.query", {
            "space_id": "patio-1", "class": "person", "cell_size_m": 0.5, **period})),
    ]
    for title, message in queries:
        producer.produce(message["schema"], value=json.dumps(message).encode("utf-8"))
        producer.flush(10)
        reply = None
        deadline = time.monotonic() + REPLY_TIMEOUT_SECONDS
        while reply is None and time.monotonic() < deadline:
            record = reader.poll(1.0)
            if record is not None and not record.error():
                candidate = json.loads(record.value())
                if candidate.get("correlation_id") == message["message_id"]:
                    reply = candidate
        print(f"\n{title}")
        if reply is None:
            print(f"   Sem reply em {REPLY_TIMEOUT_SECONDS} s.")
            reader.close()
            return 1
        show(f"{reply['schema']} (schema_version {reply['schema_version']})", reply["payload"])

    reader.close()
    print("\nDemonstração concluída.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("topicos", "executar"):
        sys.exit(__doc__)
    if sys.argv[1] == "topicos":
        create_topics(sys.argv[2])
        sys.exit(0)
    sys.exit(run(sys.argv[2]))
