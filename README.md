# S5 — Métricas e Séries Temporais (Metrics & Time Series)

> Componente da **Camada 3 (Serviço)** do Squad **MOD-2** (Mídia, Métricas e Interfaces) no projeto **ODS 2026/2**.

O serviço **S5** transforma as transições e as ocupações de zona publicadas pelo S1 (arquitetura 6c, Especificação de interfaces 1.0) em dados agregados **no tempo** (tempo de permanência, pico de ocupação, contagem de entradas) e **no espaço** (mapas de calor em coordenadas métricas de mundo, via homografia do I3). As métricas são persistidas em um armazenamento analítico colunar (**DuckDB**), consolidadas por rollup (1s → 1m → 15m → 1h) e expostas às aplicações por uma API REST.

---

## 🏗️ Arquitetura e Estrutura de Diretórios

O projeto adota os princípios de **Clean Architecture**, **Domain-Driven Design (DDD)** e **Design Patterns (GoF)**, desenvolvido em **Python 3.12**.

```text
s5/
├── README.md                   # Documentação do componente
├── app.py                      # Ponto de entrada da API (uvicorn app:app)
├── seed.py                     # Dados de exemplo para testar a API
├── requirements.txt            # Dependências (pytest, duckdb, fastapi, uvicorn, httpx)
├── pytest.ini                  # Configuração dos testes (pythonpath = .)
├── src/
│   ├── domain/                 # 1. Coração do negócio (zero dependências externas)
│   │   ├── entities/           # ZoneTransition, ZoneOccupancySample, OccupancyMetric, HeatmapGrid
│   │   ├── value_objects/      # Envelope, TimeWindow, WorldCoordinate, PixelCoordinate,
│   │   │                       #   SpatialCell, HomographyMatrix
│   │   ├── repositories/       # Contrato ITimeSeriesRepository
│   │   ├── services/           # MessageDeduplicator, AggregationStrategy,
│   │   │                       #   MovingWindowGenerator, SpatialCoordinateConverter,
│   │   │                       #   GridDensityCalculator, DownsamplingService
│   │   └── exceptions/         # Hierarquia de exceções (DomainError, ApplicationError)
│   ├── application/            # 2. Orquestração de casos de uso e DTOs
│   │   ├── use_cases/          # IngestEnvelope, AggregateZoneMetrics, GenerateHeatmap, RollupMetrics
│   │   ├── parsers/            # Leitura do envelope comum de 13 campos
│   │   └── dtos/               # OccupancyMetricDTO, HeatmapQueryDTO
│   ├── infrastructure/         # 3. Adaptadores e integrações externas
│   │   ├── b3_bus/             # Consumidor do Barramento B3 (contrato + in-memory)
│   │   ├── database/           # DuckDBTimeSeriesRepository
│   │   ├── i3_calibration/     # Carregador da matriz de homografia (JSON)
│   │   └── workers/            # DownsamplingRollupWorker
│   └── presentation/           # 4. Exposição de API
│       └── http/               # Router FastAPI (/api/v5)
└── tests/
    ├── fixtures/               # Mensagens de exemplo da Especificação 1.0
    ├── unit/                   # Domínio e casos de uso (com fakes em memória)
    └── integration/            # DuckDB real, HTTP (TestClient), B3 in-memory, calibração
```

A regra de dependência é estrita: `domain` não importa nada de fora; `application` só conhece `domain`; `infrastructure` e `presentation` implementam os contratos definidos no domínio.

---

## 🧩 Submódulos e Responsabilidades (Squad MOD-2)

Conforme definido em [`docs/responsability.md`](../docs/responsability.md):

| Submódulo | Funcionalidade | Padrão / Arquitetura | Responsável |
| :--- | :--- | :--- | :--- |
| **S5.1 — Ingestor de Eventos B3** | Consumo Pub/Sub do B3, leitura do envelope comum, deduplicação por `message_id` e conversão de `ods.s1.zone_transition` e `ods.s1.zone_occupancy`. | Event Consumer + Deduplicator | Rafael Castro |
| **S5.2 — Motor de Agregação** | Tempo de permanência (`dwell_s` do S1), pico e média de ocupação e contagem de entradas em janelas de 1m, 15m e 1h. | Time Window Engine + Aggregator Strategy | Rafael Castro |
| **S5.3 — Gerador de Mapa de Calor** | Projeção de pixels $(u, v)$ no plano de mundo pela homografia I3 ($H \in \mathbb{R}^{3\times 3}$) e cálculo de densidade em grade. | Spatial Coordinate Converter + Grid Density Calculator | Rafael Castro |
| **S5.4 — Time-Series Store (DuckDB)** | Armazenamento colunar OLAP, worker de rollup (1s → 1m → 15m → 1h) e consultas SQL de séries temporais. | DuckDB Repository + Downsampling Rollup Worker | Rafael Castro |

---

## 🔄 Fluxo de Dados

```text
Barramento B3 (ods.s1.zone_transition, ods.s1.zone_occupancy)
  └─> B3EventConsumer.subscribe(topic, handler)                    (S5.1)
        └─> IngestEnvelopeUseCase.execute(message)
              parse_envelope → Envelope (13 campos, perfil EV-SINAL)
              MessageDeduplicator → descarta message_id repetido
              payload → ZoneTransition | ZoneOccupancySample
  └─> AggregateZoneMetricsUseCase.execute(transitions, samples, zone_id, t)  (S5.2)
        MovingWindowGenerator → janelas [t-1m, t), [t-15m, t), [t-1h, t)
        ZoneOccupancyAggregationStrategy → OccupancyMetric por janela
  └─> GenerateHeatmapUseCase.execute(pixels, H, grid_id, t)        (S5.3)
        SpatialCoordinateConverter (H · [u, v, 1]ᵀ) → WorldCoordinate
        GridDensityCalculator → HeatmapGrid (densidade 0.0–1.0)
  └─> DuckDBTimeSeriesRepository                                   (S5.4)
        tabelas occupancy_metrics / heatmap_cells
        DownsamplingRollupWorker.run() → 1s → 1m → 15m → 1h
  └─> GET /api/v5/metrics/{zone_id} · GET /api/v5/heatmaps/{grid_id}
```

---

## 📥 S5.1 — Ingestor de Eventos B3

**Entrada:** mensagens do S1 com o envelope comum da Especificação de interfaces 1.0 (seção 3, perfil EV-SINAL). Exemplo de `ods.s1.zone_transition`:

```json
{
  "message_type": "event",
  "message_id": "1b2c3d4e-5f60-4a7b-8c9d-0e1f2a3b4c5d",
  "schema": "ods.s1.zone_transition",
  "schema_version": "1.0",
  "producer": "S1",
  "published_at": "2026-09-23T14:29:59.450Z",
  "captured_at": "2026-09-23T14:29:59.200Z",
  "source_id": "cam0",
  "session_id": "9c2a1f3e-4d5b-4c6a-9e8f-0a1b2c3d4e5f",
  "sequence": 1204,
  "artifact_version": "zones-a8-2",
  "payload": {
    "track_id": "t-0391", "class": "vehicle", "zone_id": "vaga-12",
    "transition": "EXIT", "entered_at": "2026-09-23T12:10:04.200Z", "dwell_s": 8395
  }
}
```

**Processamento** (`IngestEnvelopeUseCase`):
- Schema fora de `ods.s1.zone_transition` e `ods.s1.zone_occupancy` → `UnsupportedSchemaError`.
- `parse_envelope` exige os seis campos fixos e os do perfil EV-SINAL (`captured_at`, `source_id`, `session_id`, `sequence`, `artifact_version`). Marcos de tempo precisam de fuso (`Z`) e são convertidos para UTC sem `tzinfo`, convenção de todo o S5. Campo ausente ou com formato inválido → `MalformedEventEnvelopeError`.
- `MessageDeduplicator` descarta mensagens cujo `message_id` já foi aceito (regra 7) e retorna `None`. O id só é registrado depois que a mensagem é aceita.
- `schema_version` com MAJOR diferente de `1` → `UnsupportedSchemaVersionError`; qualquer MINOR do MAJOR 1 é aceito (regra 8).

Não há debounce nem histerese no S5: na 6c, a histerese é do S1, configurada pelo artefato ZONES, e a transição já chega confirmada.

**Saída:** `ZoneTransition` ou `ZoneOccupancySample`, ou `None` quando a mensagem é repetida.

O `InMemoryB3EventConsumer` implementa o contrato `B3EventConsumer` sem broker real. Ele serve para desenvolvimento e testes e é o ponto de troca por um cliente Pub/Sub de verdade. O contrato espelha o consumidor usado no S4 (C++).

## 📊 S5.2 — Motor de Agregação

**Entrada:** transições e amostras de ocupação de uma zona e um instante de referência.

**Processamento** (`ZoneOccupancyAggregationStrategy`), em janelas semiabertas `[início, fim)`:
- **Dwell time médio:** média do `dwell_s` das transições `EXIT` na janela.
- **Contagem total:** número de transições `ENTER` na janela.
- **Pico de ocupação:** maior `count` vigente na janela.
- **Ocupação média:** `count` médio ponderado pelo tempo em que cada amostra vigorou. A contagem no início da janela é a da última amostra anterior a ela; sem amostra anterior, a zona é considerada vazia.

As janelas padrão são **1m, 15m e 1h**, gravadas com as granularidades `"1m"`, `"15m"` e `"1h"`.

**Saída:** `OccupancyMetricDTO { zone_id, dwell_time_avg, occupancy_peak, total_count, occupancy_avg }` por janela.

## 🗺️ S5.3 — Gerador de Mapa de Calor

**Entrada:** coordenadas de pixel `PixelCoordinate(u, v)` + `HomographyMatrix` 3×3 do I3.

**Processamento:**
- `HomographyMatrix.project()` multiplica $H \cdot [u, v, 1]^T$ e divide por $w$, o que dá a posição em metros no plano do mundo. Se $w = 0$, a projeção é rejeitada.
- `GridDensityCalculator(cell_size)` agrupa os pontos em células regulares e normaliza a densidade pelo pico (a célula mais cheia fica com `1.0`).
- `HomographyCalibratorAdapter` carrega a matriz de um arquivo JSON de calibração:

```json
{ "homography_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]] }
```

**Saída:** `HeatmapQueryDTO { grid_id, cells: [(x, y, density), ...] }`.

## 🗄️ S5.4 — Time-Series Store (DuckDB)

**Tabelas:**

| Tabela | Colunas |
| :--- | :--- |
| `occupancy_metrics` | `zone_id`, `granularity`, `start_time`, `end_time`, `dwell_time_avg`, `occupancy_peak`, `total_count`, `occupancy_avg` |
| `heatmap_cells` | `grid_id`, `timestamp`, `x`, `y`, `density` |

**Rollup:** `DownsamplingRollupWorker.run(zone_id, reference_time)` encadeia `1s → 1m → 15m → 1h`. Ele deve ser disparado por um cron externo. Em cada salto, `DownsamplingService` consolida as métricas finas assim:
- `total_count`: soma;
- `occupancy_peak`: máximo;
- `dwell_time_avg`: média **ponderada** por `total_count`;
- `occupancy_avg`: média ponderada pela duração de cada janela fina.

Bancos criados antes de `occupancy_avg` existir recebem a coluna na abertura, com valor `0`.

**API REST** (`create_metrics_query_router(repository)`, prefixo `/api/v5`):

| Método | Rota | Parâmetros | Resposta |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v5/metrics/{zone_id}` | `start_time`, `end_time` (ISO 8601), `granularity` (padrão `1m`) | `list[OccupancyMetricDTO]` |
| `GET` | `/api/v5/heatmaps/{grid_id}` | `start_time`, `end_time` (ISO 8601) | `list[HeatmapQueryDTO]` |

---

## 🚀 Como Executar

### Instalação

```bash
cd s5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Testes

```bash
pytest            # suíte completa
pytest tests/unit # somente testes unitários
```

Os testes unitários usam fakes em memória ([`tests/unit/application/fakes.py`](tests/unit/application/fakes.py)). Os de integração usam DuckDB real (`:memory:`), o `TestClient` do FastAPI e o consumidor B3 em memória.

### Subindo a API

O ponto de entrada é [`app.py`](app.py), que monta o router sobre um `DuckDBTimeSeriesRepository`. O banco padrão é `s5_metrics.db`; para usar outro caminho (ou `:memory:`), defina `S5_DATABASE_PATH`.

```bash
uvicorn app:app --reload
# http://localhost:8000/docs
```

O banco começa vazio e a API é somente leitura. Para ter dados de exemplo (`zona-1` e `grid-1` em 2026-10-09), rode antes `python seed.py` e consulte:

```bash
curl "http://localhost:8000/api/v5/metrics/zona-1?start_time=2026-10-09T00:00:00&end_time=2026-10-09T23:59:59"
curl "http://localhost:8000/api/v5/heatmaps/grid-1?start_time=2026-10-09T00:00:00&end_time=2026-10-09T23:59:59"
```

---

## ✅ Validação

| Verificação | Resultado |
| :--- | :--- |
| `pytest` (unitários + integração) | 99/99 aprovados |
| Invariantes de domínio | Coordenadas não finitas, janelas invertidas, densidades negativas, matrizes fora de 3×3, IDs vazios, envelopes fora do contrato e `EXIT` sem `dwell_s` lançam exceções específicas de `DomainError` |
| Contrato de entrada | Exemplos de `ods.s1.zone_transition` e `ods.s1.zone_occupancy` da Especificação 1.0, deduplicação por `message_id` e regra de MAJOR.MINOR |
| Persistência DuckDB | Escrita e consulta por zona, granularidade e intervalo de tempo |
| API HTTP | Rotas `/api/v5/metrics` e `/api/v5/heatmaps` testadas via `TestClient` |
