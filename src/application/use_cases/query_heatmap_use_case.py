from src.application.use_cases.query_metrics_use_case import INVALID_QUERY, parse_period
from src.domain.exceptions import QueryRejectedError
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.presence_accumulator import BASE_CELL_SIZE, METERS, PIXELS

MAX_GRID_SIDE = 200
GRID_TOO_LARGE = "GRID_TOO_LARGE"


class QueryHeatmapUseCase:
    """Atende ods.s5.heatmap.query: segundos de presença por célula no período.

    Em metros, pede space_id e cell_size_m; em instalação sem calibração, source_id e
    cell_size_px. A presença é guardada em células finas (0,1 m ou 10 px) e agrupada aqui
    no tamanho pedido, que precisa ser um múltiplo da resolução base: assim cada célula
    fina cai inteira em uma célula pedida. A grade cobre só o retângulo com presença:
    origin é o canto da primeira célula e cells[y][x] os segundos.

    Grades acima de 200×200 deveriam ir por heatmap_uri; o S5 ainda não tem onde guardar
    o arquivo, então recusa com GRID_TOO_LARGE e pede célula maior.
    """

    def __init__(self, repository: ITimeSeriesRepository) -> None:
        self._repository = repository

    def execute(self, payload: dict) -> dict:
        kind, space_key, size_field = self._space(payload)
        cell_size = payload[size_field]
        if isinstance(cell_size, bool) or not isinstance(cell_size, (int, float)):
            raise QueryRejectedError(INVALID_QUERY, f"{size_field} deve ser numérico.")
        cells_per_group = _cells_per_group(cell_size, BASE_CELL_SIZE[kind])
        if cells_per_group is None:
            raise QueryRejectedError(
                INVALID_QUERY,
                f"{size_field} deve ser múltiplo de {BASE_CELL_SIZE[kind]} (ex.: "
                f"{BASE_CELL_SIZE[kind] * 5:g}), recebido {cell_size}.",
            )
        period = parse_period(payload)

        fine_cells = self._repository.query_presence(
            kind, space_key, period, object_class=payload.get("class")
        )
        totals: dict[tuple[int, int], float] = {}
        for cell_x, cell_y, seconds in fine_cells:
            key = (cell_x // cells_per_group, cell_y // cells_per_group)
            totals[key] = totals.get(key, 0.0) + seconds

        if not totals:
            return {"grid_width": 0, "grid_height": 0, size_field: cell_size, "origin": [0.0, 0.0], "cells": []}

        min_x = min(x for x, _ in totals)
        min_y = min(y for _, y in totals)
        width = max(x for x, _ in totals) - min_x + 1
        height = max(y for _, y in totals) - min_y + 1
        if width > MAX_GRID_SIDE or height > MAX_GRID_SIDE:
            raise QueryRejectedError(
                GRID_TOO_LARGE,
                f"Grade de {width}×{height} acima de {MAX_GRID_SIDE}×{MAX_GRID_SIDE}; use célula maior.",
            )

        cells = [[0] * width for _ in range(height)]
        for (x, y), seconds in totals.items():
            cells[y - min_y][x - min_x] = round(seconds)
        return {
            "grid_width": width,
            "grid_height": height,
            size_field: cell_size,
            "origin": [min_x * cell_size, min_y * cell_size],
            "cells": cells,
        }

    @staticmethod
    def _space(payload: dict) -> tuple[str, str, str]:
        if payload.get("space_id") and "cell_size_m" in payload:
            return METERS, payload["space_id"], "cell_size_m"
        if payload.get("source_id") and "cell_size_px" in payload:
            return PIXELS, payload["source_id"], "cell_size_px"
        raise QueryRejectedError(
            INVALID_QUERY, "Informe space_id com cell_size_m, ou source_id com cell_size_px."
        )



def _cells_per_group(cell_size: float, base: float) -> int | None:
    """Quantas células finas cabem em cada lado da célula pedida, ou None se o tamanho
    pedido não for um múltiplo inteiro e positivo da resolução base. A tolerância cobre
    o arredondamento binário de valores como 0.3 / 0.1 = 2.9999…"""
    ratio = cell_size / base
    count = round(ratio)
    if count < 1 or abs(ratio - count) > 1e-9:
        return None
    return count
