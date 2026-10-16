from collections import OrderedDict


class MessageDeduplicator:
    """Lembra os message_id já processados para descartar reentregas (regra 7).

    A memória é limitada: guarda os `capacity` ids mais recentes, o que cobre a janela
    de reentrega do barramento sem crescer indefinidamente na Jetson.
    """

    def __init__(self, capacity: int = 100_000) -> None:
        if capacity <= 0:
            raise ValueError("capacity deve ser maior que zero.")
        self._capacity = capacity
        self._seen: OrderedDict[str, None] = OrderedDict()

    def is_duplicate(self, message_id: str) -> bool:
        return message_id in self._seen

    def register(self, message_id: str) -> None:
        self._seen[message_id] = None
        self._seen.move_to_end(message_id)
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
