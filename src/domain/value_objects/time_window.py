from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import InvalidTimeWindowError


@dataclass(frozen=True)
class TimeWindow:
    """Uma janela de tempo, do start_time (começo) ao end_time (fim)."""

    start_time: datetime
    end_time: datetime

    def __post_init__(self) -> None:
        if self.start_time >= self.end_time:
            raise InvalidTimeWindowError(
                f"start_time deve ser anterior a end_time, recebido {self.start_time} / {self.end_time}."
            )

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()