"""Adaptador do Kafka com consumidor e produtor falsos, sem broker. O teste contra um
broker real está em test_kafka_b3_bus_real.py e só roda com S5_TEST_KAFKA_BROKERS."""

import json
import threading

import pytest
from confluent_kafka import KafkaError

from src.infrastructure.b3_bus.kafka_b3_bus import KafkaB3Bus


class FakeRecord:
    def __init__(self, topic=None, value=None, error=None):
        self._topic, self._value, self._error = topic, value, error

    def topic(self):
        return self._topic

    def value(self):
        return self._value

    def error(self):
        return self._error


class FakeConsumer:
    def __init__(self, config):
        self.config = config
        self.topics = None
        self.records = []
        self.polls = []
        self.closed = False
        self.drained = threading.Event()

    def subscribe(self, topics):
        self.topics = topics

    def poll(self, timeout):
        self.polls.append(timeout)
        if self.records:
            return self.records.pop(0)
        self.drained.set()
        threading.Event().wait(0.001)
        return None

    def close(self):
        self.closed = True


class FakeProducer:
    def __init__(self, config):
        self.config = config
        self.produced = []
        self.flushed = False
        self.full = False

    def produce(self, topic, value, on_delivery):
        if self.full:
            raise BufferError
        self.produced.append((topic, value))

    def poll(self, timeout):
        return 0

    def flush(self, timeout):
        self.flushed = True
        return 0


def _bus(records=(), **options):
    consumers, producers = [], []

    def make_consumer(config):
        consumer = FakeConsumer(config)
        consumer.records = list(records)
        consumers.append(consumer)
        return consumer

    def make_producer(config):
        producers.append(FakeProducer(config))
        return producers[-1]

    bus = KafkaB3Bus(
        "broker:9093", consumer_factory=make_consumer, producer_factory=make_producer, **options
    )
    return bus, consumers, producers


def _record(topic, message):
    return FakeRecord(topic, json.dumps(message).encode("utf-8"))


def _run_until_drained(bus, consumers):
    bus.start()
    assert consumers[0].drained.wait(5)
    bus.stop()


def test_deve_configurar_o_cliente_e_assinar_os_topicos():
    bus, consumers, producers = _bus()
    bus.subscribe("ods.s2.event", lambda m: None)
    bus.subscribe("ods.s1.position", lambda m: None)

    _run_until_drained(bus, consumers)

    assert consumers[0].topics == ["ods.s1.position", "ods.s2.event"]
    assert consumers[0].config == {
        "bootstrap.servers": "broker:9093",
        "group.id": "S5-metricas",
        "client.id": "s5",
        "auto.offset.reset": "latest",
    }
    assert producers[0].config["bootstrap.servers"] == "broker:9093"


def test_deve_entregar_ao_handler_do_topico_a_mensagem_decodificada():
    bus, consumers, _ = _bus([_record("ods.s2.event", {"a": 1}), _record("ods.s1.position", {"b": 2})])
    events, positions = [], []
    bus.subscribe("ods.s2.event", events.append)
    bus.subscribe("ods.s1.position", positions.append)

    _run_until_drained(bus, consumers)

    assert events == [{"a": 1}] and positions == [{"b": 2}]


def test_deve_descartar_mensagem_que_nao_e_json_de_objeto_e_seguir_lendo():
    bus, consumers, _ = _bus(
        [
            FakeRecord("t", b"nao e json"),
            FakeRecord("t", b"\xff\xfe"),
            FakeRecord("t", None),
            _record("t", [1, 2]),
            _record("t", {"ok": True}),
        ]
    )
    received = []
    bus.subscribe("t", received.append)

    _run_until_drained(bus, consumers)

    assert received == [{"ok": True}]


def test_erro_em_um_handler_nao_interrompe_a_leitura():
    bus, consumers, _ = _bus([_record("t", {"n": 1}), _record("t", {"n": 2})])
    received = []

    def handler(message):
        if message["n"] == 1:
            raise RuntimeError("falha")
        received.append(message)

    bus.subscribe("t", handler)

    _run_until_drained(bus, consumers)

    assert received == [{"n": 2}]


def test_erro_repetido_do_broker_e_registrado_uma_vez(caplog):
    error = KafkaError(KafkaError.UNKNOWN_TOPIC_OR_PART)
    bus, consumers, _ = _bus([FakeRecord(error=error), FakeRecord(error=error)])
    bus.subscribe("t", lambda m: None)

    _run_until_drained(bus, consumers)

    assert len([r for r in caplog.records if "Erro do Kafka" in r.message]) == 1


def test_deve_publicar_json_em_utf8_no_topico():
    bus, consumers, producers = _bus()
    bus.subscribe("t", lambda m: None)
    bus.start()
    bus.publish("ods.s5.zone_metrics", {"zona": "galpão"})
    consumers[0].drained.wait(5)
    bus.stop()

    [(topic, value)] = producers[0].produced
    assert topic == "ods.s5.zone_metrics"
    assert json.loads(value.decode("utf-8")) == {"zona": "galpão"}


def test_fila_local_cheia_descarta_e_registra_sem_derrubar_quem_publicou(caplog):
    bus, consumers, producers = _bus()
    bus.start()
    producers[0].full = True

    bus.publish("t", {})
    bus.stop()

    assert any("fila local" in r.message for r in caplog.records)


def test_publicar_com_o_barramento_parado_nao_falha(caplog):
    bus, _, _ = _bus()
    bus.publish("t", {})
    assert any("barramento parado" in r.message for r in caplog.records)


def test_stop_fecha_o_consumidor_e_esvazia_o_produtor():
    bus, consumers, producers = _bus()
    bus.start()
    bus.stop()

    assert consumers[0].closed and producers[0].flushed
    assert all(timeout >= 1.0 for timeout in consumers[0].polls)


def test_deve_recusar_poll_menor_que_um_segundo_e_endereco_vazio():
    with pytest.raises(ValueError):
        KafkaB3Bus("broker:9093", poll_seconds=0.1)
    with pytest.raises(ValueError):
        KafkaB3Bus("  ")


def test_nao_aceita_assinatura_depois_de_iniciar():
    bus, _, _ = _bus()
    bus.start()
    with pytest.raises(RuntimeError):
        bus.subscribe("t", lambda m: None)
    bus.stop()
