import json
import logging
import threading
from collections.abc import Callable

from confluent_kafka import Consumer, KafkaError, Producer

from src.application.ports.event_publisher import IEventPublisher
from src.infrastructure.b3_bus.b3_event_consumer import B3EventConsumer, EventHandler

logger = logging.getLogger(__name__)

DEFAULT_GROUP_ID = "S5-metricas"
DEFAULT_CLIENT_ID = "s5"
DEFAULT_OFFSET_RESET = "latest"
# O guia do Kafka pede poll de pelo menos 1 s: o broker é pago e compartilhado.
MIN_POLL_SECONDS = 1.0
# Com o padrão do Kafka (5 min), um tópico criado depois da assinatura levaria minutos para
# ser descoberto: medido em 210 s para um tópico criado 90 s após assinar. Os tópicos ods.s1.*
# nascem quando o S1 começa a publicar, com o S5 possivelmente já no ar.
TOPIC_REFRESH_MS = 30_000
FLUSH_SECONDS = 5.0
JOIN_SECONDS = 10.0


class KafkaB3Bus(B3EventConsumer, IEventPublisher):
    """Barramento B3 sobre Kafka (confluent-kafka), conforme o Guia de Uso do Kafka: um
    tópico por schema, group.id próprio, endereço do broker sempre vindo de configuração.

    As mensagens são lidas em uma thread própria e os handlers executam nela. Sem posição
    salva, o grupo começa em `latest`: o S5 acompanha o presente, e ler o histórico
    inteiro responderia a consultas antigas e recalcularia métricas de sessões encerradas.
    Por isso, o que for publicado em um tópico novo antes de o S5 descobri-lo (até 30 s) é
    perdido para o S5.

    Mensagem que não é JSON de um objeto é descartada e registrada (1º nível de validação
    do guia); os níveis seguintes são dos handlers. Erro em um handler é registrado e não
    interrompe a leitura das mensagens seguintes.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str = DEFAULT_GROUP_ID,
        client_id: str = DEFAULT_CLIENT_ID,
        auto_offset_reset: str = DEFAULT_OFFSET_RESET,
        poll_seconds: float = MIN_POLL_SECONDS,
        consumer_factory: Callable[[dict], Consumer] = Consumer,
        producer_factory: Callable[[dict], Producer] = Producer,
    ) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("bootstrap_servers não pode ser vazio.")
        if poll_seconds < MIN_POLL_SECONDS:
            raise ValueError(f"poll_seconds deve ser de pelo menos {MIN_POLL_SECONDS} s.")
        self._consumer_config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "client.id": client_id,
            "auto.offset.reset": auto_offset_reset,
            "topic.metadata.refresh.interval.ms": TOPIC_REFRESH_MS,
        }
        self._producer_config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": f"{client_id}-producer",
        }
        self._poll_seconds = poll_seconds
        self._consumer_factory = consumer_factory
        self._producer_factory = producer_factory
        self._handlers: dict[str, list[EventHandler]] = {}
        self._consumer: Consumer | None = None
        self._producer: Producer | None = None
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._reported_errors: set[str] = set()

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        if self._thread is not None:
            raise RuntimeError("Assine os tópicos antes de iniciar o barramento.")
        self._handlers.setdefault(topic, []).append(handler)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stopping.clear()
        self._producer = self._producer_factory(self._producer_config)
        self._consumer = self._consumer_factory(self._consumer_config)
        self._consumer.subscribe(sorted(self._handlers))
        self._thread = threading.Thread(target=self._read_loop, name="s5-kafka", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stopping.set()
        self._thread.join(timeout=JOIN_SECONDS)
        self._thread = None
        self._consumer.close()
        self._consumer = None
        undelivered = self._producer.flush(FLUSH_SECONDS)
        if undelivered:
            logger.error("%d mensagens não foram entregues ao Kafka antes de encerrar.", undelivered)
        self._producer = None

    def publish(self, topic: str, message: dict) -> None:
        if self._producer is None:
            logger.error("Mensagem descartada: barramento parado (tópico %s).", topic)
            return
        value = json.dumps(message, ensure_ascii=False).encode("utf-8")
        try:
            self._producer.produce(topic, value=value, on_delivery=_log_delivery_failure)
        except BufferError:
            logger.error("Mensagem descartada: fila local do Kafka cheia (tópico %s).", topic)
        self._producer.poll(0)

    def _read_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                record = self._consumer.poll(self._poll_seconds)
                if record is not None:
                    self._handle_record(record)
            except Exception:  # um erro inesperado não pode encerrar a leitura em silêncio
                logger.exception("Falha ao processar mensagem do Kafka.")

    def _handle_record(self, record) -> None:
        error = record.error()
        if error is not None:
            self._report_error(error)
            return
        topic = record.topic()
        try:
            message = json.loads(record.value().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as decode_error:
            logger.warning("Mensagem descartada no tópico %s: não é JSON (%s).", topic, decode_error)
            return
        if not isinstance(message, dict):
            logger.warning("Mensagem descartada no tópico %s: o JSON não é um objeto.", topic)
            return
        for handler in self._handlers.get(topic, []):
            handler(message)

    def _report_error(self, error: KafkaError) -> None:
        """Cada erro é registrado uma vez: um tópico que ainda não existe ou um broker fora
        do ar repetem o mesmo erro indefinidamente."""
        if error.code() == KafkaError._PARTITION_EOF or str(error) in self._reported_errors:
            return
        self._reported_errors.add(str(error))
        logger.warning("Erro do Kafka: %s", error)


def _log_delivery_failure(error, record) -> None:
    if error is not None:
        logger.error("Falha ao entregar mensagem no tópico %s: %s", record.topic(), error)
