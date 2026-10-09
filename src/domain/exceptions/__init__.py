class ODSBaseException(Exception):
    """Exceção base para todo o sistema ODS."""


class DomainError(ODSBaseException):
    """Erros de violação de regras de negócio do domínio."""


class InvalidWorldCoordinateError(DomainError):
    """Lançado quando uma coordenada de mundo recebe valores não finitos (NaN/inf)."""


class InvalidSpatialCellError(DomainError):
    """Lançado quando uma célula recebe densidade negativa ou não finita."""


class InvalidTimeWindowError(DomainError):
    """Lançado quando start_time é maior ou igual a end_time."""


class InvalidNormalizedEventError(DomainError):
    """Lançado quando um evento normalizado recebe event_type ou origin vazios."""


class InvalidOccupancyMetricError(DomainError):
    """Lançado quando uma métrica de ocupação recebe zone_id vazio ou valores negativos."""


class InvalidPixelCoordinateError(DomainError):
    """Lançado quando uma coordenada de pixel recebe valores não finitos (NaN/inf)."""


class InvalidHomographyMatrixError(DomainError):
    """Lançado quando a matriz de homografia não é 3x3 ou contém valores não finitos."""


class InvalidHeatmapGridError(DomainError):
    """Lançado quando uma grade de mapa de calor recebe grid_id vazio."""


class ApplicationError(ODSBaseException):
    """Erros na camada de casos de uso."""


class MalformedEventEnvelopeError(ApplicationError):
    """Lançado quando o envelope B1/B3 não contém os campos obrigatórios para normalização."""