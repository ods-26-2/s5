from collections.abc import Callable
from datetime import datetime, timezone

from src.application.use_cases.close_metric_windows_use_case import CloseMetricWindowsUseCase


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MetricsWindowWorker:
    """Dispara o fechamento das janelas. Deve ser chamado por um agendador externo em
    intervalo menor que a menor janela (ex.: a cada 5 s); disparos extras não publicam
    nada, porque só fecham janelas que terminaram desde o disparo anterior."""

    def __init__(
        self, close_windows: CloseMetricWindowsUseCase, clock: Callable[[], datetime] = _utc_now
    ) -> None:
        self._close_windows = close_windows
        self._clock = clock

    def run(self) -> list[dict]:
        return self._close_windows.execute(self._clock())
