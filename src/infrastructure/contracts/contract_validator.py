import json
import logging
from collections.abc import Callable
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from src.application.ports.event_publisher import IEventPublisher
from src.domain.exceptions import ContractViolationError

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
SCHEMA_SUFFIX = ".schema.json"
DEFS_FILE = "s5.defs.schema.json"

logger = logging.getLogger(__name__)
ViolationCallback = Callable[[dict, ContractViolationError], None]


class ContractValidator:
    """Valida mensagens contra os JSON Schemas de contracts/, escolhendo o schema pelo
    campo `schema` da própria mensagem. Cada arquivo ods.*.schema.json é um contrato;
    s5.defs.schema.json só guarda definições compartilhadas."""

    def __init__(self, contracts_dir: Path = CONTRACTS_DIR) -> None:
        documents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(contracts_dir.glob(f"*{SCHEMA_SUFFIX}"))
        }
        registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document)) for document in documents.values()
        )
        self._validators = {}
        for name, document in documents.items():
            Draft202012Validator.check_schema(document)
            if name != DEFS_FILE:
                schema_name = name.removesuffix(SCHEMA_SUFFIX)
                self._validators[schema_name] = Draft202012Validator(document, registry=registry)

    @property
    def schemas(self) -> tuple[str, ...]:
        return tuple(sorted(self._validators))

    def problems(self, message: dict) -> list[str]:
        """Lista os desvios da mensagem em relação ao contrato; vazia se ela é válida."""
        schema = message.get("schema") if isinstance(message, dict) else None
        validator = self._validators.get(schema)
        if validator is None:
            return [f"não há contrato para o schema {schema!r}"]
        return [
            f"{'/'.join(str(part) for part in error.absolute_path) or '(raiz)'}: {error.message}"
            for error in sorted(validator.iter_errors(message), key=lambda e: list(e.absolute_path))
        ]

    def validate(self, message: dict) -> None:
        problems = self.problems(message)
        if problems:
            raise ContractViolationError(message.get("schema") if isinstance(message, dict) else None, problems)


def _log_violation(message: dict, error: ContractViolationError) -> None:
    logger.error(
        "Mensagem fora do contrato descartada antes de publicar (message_id=%s): %s",
        message.get("message_id"),
        error,
    )


class ValidatingPublisher(IEventPublisher):
    """Validador no publicador (Especificação 1.0, seção 2): toda mensagem do S5 é
    conferida contra o seu contrato antes de ir ao barramento, e a que não segue o
    contrato nunca chega a ele.

    A mensagem rejeitada é descartada e entregue a `on_violation` (por padrão, o log de
    erro) em vez de interromper quem publicou. Uma violação é erro de programação, não
    falha passageira; interromper o fechamento de janelas faria o próximo disparo
    regravar as mesmas métricas no banco.
    """

    def __init__(
        self,
        inner: IEventPublisher,
        validator: ContractValidator,
        on_violation: ViolationCallback = _log_violation,
    ) -> None:
        self._inner = inner
        self._validator = validator
        self._on_violation = on_violation

    def publish(self, topic: str, message: dict) -> None:
        problems = self._validator.problems(message)
        if topic != message.get("schema"):
            problems.append(f"tópico {topic!r} diferente do schema {message.get('schema')!r}")
        if problems:
            self._on_violation(message, ContractViolationError(message.get("schema"), problems))
            return
        self._inner.publish(topic, message)
