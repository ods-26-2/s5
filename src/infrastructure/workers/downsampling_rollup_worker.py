from datetime import datetime

from src.application.use_cases.rollup_metrics_use_case import RollupMetricsUseCase
from src.domain.services.moving_window_generator import MovingWindowGenerator

ROLLUP_CHAIN = (
    ("1s", "1m", 60),
    ("1m", "15m", 900),
    ("15m", "1h", 3600),
)


class DownsamplingRollupWorker:
    """Orquestra o encadeamento de rollups 1s -> 1m -> 15m -> 1h a cada disparo do
    cron trigger externo, consolidando a granularidade mais fina disponível em cada salto."""

    def __init__(
        self, rollup_use_case: RollupMetricsUseCase, window_generator: MovingWindowGenerator
    ) -> None:
        self._rollup_use_case = rollup_use_case
        self._window_generator = window_generator

    def run(self, zone_id: str, reference_time: datetime) -> None:
        for source_granularity, target_granularity, window_seconds in ROLLUP_CHAIN:
            window = self._window_generator.generate(reference_time, [window_seconds])[0]
            self._rollup_use_case.execute(
                zone_id=zone_id,
                source_granularity=source_granularity,
                source_window=window,
                target_granularity=target_granularity,
                target_window=window,
            )
