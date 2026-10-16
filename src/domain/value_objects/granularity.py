from datetime import datetime, timedelta

from src.domain.exceptions import InvalidGranularityError
from src.domain.value_objects.time_window import TimeWindow

GRANULARITY_SECONDS = {"1m": 60, "15m": 900, "1h": 3600, "1d": 86400}
EPOCH = datetime(1970, 1, 1)


def closed_windows(granularity: str, since: datetime, until: datetime) -> list[TimeWindow]:
    """Janelas da granularidade, alinhadas ao relógio UTC (14:00–14:15, não t-15m–t), cujo
    fim cai em (since, until]: são as que fecharam entre os dois instantes."""
    if granularity not in GRANULARITY_SECONDS:
        raise InvalidGranularityError(
            f"Granularidade {granularity!r} fora de {sorted(GRANULARITY_SECONDS)}."
        )
    size = timedelta(seconds=GRANULARITY_SECONDS[granularity])
    end = EPOCH + ((since - EPOCH) // size + 1) * size
    windows = []
    while end <= until:
        windows.append(TimeWindow(start_time=end - size, end_time=end))
        end += size
    return windows
