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


class InvalidEnvelopeError(DomainError):
    """Lançado quando o envelope comum (Especificação 1.0, seção 3) viola suas regras:
    message_type fora do enum, identificadores vazios ou schema_version fora de MAJOR.MINOR."""


class InvalidZoneTransitionError(DomainError):
    """Lançado quando uma transição de zona de S1 tem sentido inválido, ids vazios ou
    EXIT sem dwell_s."""


class InvalidZoneOccupancyError(DomainError):
    """Lançado quando uma amostra de ocupação de S1 tem zone_id vazio ou contagem negativa."""


class InvalidQualifiedEventError(DomainError):
    """Lançado quando um evento qualificado de S2 tem status ou phase fora do enum,
    ids vazios ou duração negativa."""


class InvalidEventMetricError(DomainError):
    """Lançado quando uma métrica por tipo de evento tem event_type vazio ou contagens
    incoerentes."""


class InvalidGranularityError(DomainError):
    """Lançado quando a granularidade não é uma de 1m, 15m, 1h e 1d."""


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
    """Lançado quando a mensagem não contém os campos obrigatórios do envelope, do perfil
    ou do payload, ou quando um campo tem tipo ou formato inválido."""


class UnsupportedSchemaError(ApplicationError):
    """Lançado quando chega uma mensagem de um schema que o S5 não consome."""


class UnsupportedSchemaVersionError(ApplicationError):
    """Lançado quando o MAJOR de schema_version é diferente do que o S5 conhece (regra 8)."""