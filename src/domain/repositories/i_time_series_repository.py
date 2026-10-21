from abc import ABC, abstractmethod

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.entities.session_start import LIVE
from src.domain.services.presence_accumulator import PresenceKey
from src.domain.value_objects.time_window import TimeWindow


class ITimeSeriesRepository(ABC):
    """Contrato de persistência de séries temporais, isolando o domínio do DuckDB.

    Cada métrica é gravada com o modo (LIVE ou REPLAY) e a sessão que a produziram. Um
    replay reproduz o tempo de captura original, então as janelas dele coincidem com as
    da captura ao vivo daquele dia; as consultas leem só LIVE salvo pedido explícito,
    para que um replay não duplique o histórico.
    """

    @abstractmethod
    def save_occupancy_metric(
        self,
        metric: OccupancyMetric,
        granularity: str,
        mode: str = LIVE,
        session_id: str | None = None,
    ) -> None: ...

    @abstractmethod
    def save_event_metric(
        self,
        metric: EventMetric,
        granularity: str,
        mode: str = LIVE,
        session_id: str | None = None,
    ) -> None: ...

    @abstractmethod
    def save_presence(self, cells: list[tuple[PresenceKey, float, str]]) -> None:
        """Grava segundos de presença por célula fina e minuto; cada item traz o modo
        (LIVE ou REPLAY) da sessão da chave."""

    @abstractmethod
    def query_presence(
        self,
        space_kind: str,
        space_key: str,
        window: TimeWindow,
        object_class: str | None = None,
        mode: str = LIVE,
    ) -> list[tuple[int, int, float]]:
        """Soma da presença no período por célula fina: (cell_x, cell_y, segundos)."""

    @abstractmethod
    def query_zone_series(
        self, window: TimeWindow, granularity: str, zone_id: str | None = None, mode: str = LIVE
    ) -> list[OccupancyMetric]: ...

    @abstractmethod
    def query_event_series(
        self,
        window: TimeWindow,
        granularity: str,
        event_type: str | None = None,
        zone_id: str | None = None,
        object_class: str | None = None,
        mode: str = LIVE,
    ) -> list[EventMetric]: ...

    @abstractmethod
    def zone_exists(self, zone_id: str) -> bool:
        """Se há alguma métrica gravada para a zona, em qualquer modo."""
