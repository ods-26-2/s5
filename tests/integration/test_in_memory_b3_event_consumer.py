from src.infrastructure.b3_bus.b3_event_consumer import InMemoryB3EventConsumer


def test_deve_entregar_envelope_para_handler_inscrito_quando_consumer_estiver_rodando():
    consumer = InMemoryB3EventConsumer()
    received = []
    consumer.subscribe("b3.events", received.append)
    consumer.start()

    consumer.publish("b3.events", {"event_type": "enter"})

    assert received == [{"event_type": "enter"}]


def test_nao_deve_entregar_envelope_quando_consumer_nao_estiver_rodando():
    consumer = InMemoryB3EventConsumer()
    received = []
    consumer.subscribe("b3.events", received.append)

    consumer.publish("b3.events", {"event_type": "enter"})

    assert received == []


def test_nao_deve_entregar_envelope_apos_stop():
    consumer = InMemoryB3EventConsumer()
    received = []
    consumer.subscribe("b3.events", received.append)
    consumer.start()
    consumer.stop()

    consumer.publish("b3.events", {"event_type": "enter"})

    assert received == []
