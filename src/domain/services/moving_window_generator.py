from datetime import datetime, timedelta

from src.domain.value_objects.time_window import TimeWindow


class MovingWindowGenerator:
    """Gera janelas de tempo móveis (ex.: 1m, 15m, 1h) terminando em um instante de referência."""

    def generate(self, reference_time: datetime, sizes_seconds: list[int]) -> list[TimeWindow]:
        return [
            TimeWindow(
                start_time=reference_time - timedelta(seconds=size_seconds),
                end_time=reference_time,
            )
            for size_seconds in sizes_seconds
        ]
