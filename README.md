# S5 — Métricas e Séries Temporais (Metrics & Time Series)

> Componente da **Camada 3 (Serviço)** do Squad **MOD-2** (Mídia, Métricas e Interfaces) no projeto **ODS 2026/2**.

O serviço **S5** transforma eventos brutos e ruidosos do Barramento B3 em dados agregados **no tempo** (tempo de permanência, pico de ocupação, contagem de entradas) e **no espaço** (mapas de calor em coordenadas métricas de mundo, via homografia do I3). As métricas são persistidas em um armazenamento analítico colunar (**DuckDB**), consolidadas por rollup (1s → 1m → 15m → 1h) e expostas às aplicações por uma API REST.

---

## 🏗️ Arquitetura e Estrutura de Diretórios

O projeto adota os princípios de **Clean Architecture**, **Domain-Driven Design (DDD)** e **Design Patterns (GoF)**, desenvolvido em **Python 3.12**.

```text
s5/
├── README.md                   # Documentação do componente
├── requirements.txt            # Dependências (pytest, duckdb, fastapi, uvicorn, httpx)
├── pytest.ini                  # Configuração dos testes (pythonpath = .)
├── src/
│   ├── domain/                 # 1. Coração do negócio (zero dependências externas)
│   │   ├── entities/           # NormalizedEvent, OccupancyMetric, HeatmapGrid
│   │   ├── value_objects/      # TimeWindow, WorldCoordinate, PixelCoordinate,
│   │   │                       #   SpatialCell, HomographyMatrix
│   │   ├── repositories/       # Contrato ITimeSeriesRepository
│   │   ├── services/           # EventFilterStrategy, AggregationStrategy,
│   │   │                       #   MovingWindowGenerator, SpatialCoordinateConverter,
│   │   │                       #   GridDensityCalculator, DownsamplingService
│   │   └── exceptions/         # Hierarquia de exceções (DomainError, ApplicationError)
│   ├── application/            # 2. Orquestração de casos de uso e DTOs
│   │   ├── use_cases/          # IngestEvent, AggregateDwellTime, GenerateHeatmap, RollupMetrics
│   │   └── dtos/               # OccupancyMetricDTO, HeatmapQueryDTO
│   ├── infrastructure/         # 3. Adaptadores e integrações externas
│   │   ├── b3_bus/             # Consumidor do Barramento B3 (contrato + in-memory)
│   │   ├── database/           # DuckDBTimeSeriesRepository
│   │   ├── i3_calibration/     # Carregador da matriz de homografia (JSON)
│   │   └── workers/            # DownsamplingRollupWorker
│   └── presentation/           # 4. Exposição de API
│       └── http/               # Router FastAPI (/api/v5)
└── tests/
    ├── unit/                   # Domínio e casos de uso (com fakes em memória)
    └── integration/            # DuckDB real, HTTP (TestClient), B3 in-memory, calibração
```

A regra de dependência é estrita: `domain` não importa nada de fora; `application` só conhece `domain`; `infrastructure` e `presentation` implementam os contratos definidos no domínio.

---

## 🧩 Submódulos e Responsabilidades (Squad MOD-2)

Conforme definido em [`docs/responsability.md`](../docs/responsability.md):

| Submódulo | Funcionalidade | Padrão / Arquitetura | Responsável |
| :--- | :--- | :--- | :--- |
| **S5.1 — Ingestor de Eventos B3** | Consumo Pub/Sub do B3, parsing do envelope B1/B3 e debounce/histerese contra ruído na borda das zonas. | Event Consumer + Filter Strategy | Rafael Castro |
| **S5.2 — Motor de Agregação** | Tempo de permanência (dwell time), pico de ocupação simultânea e contagem total em janelas móveis de 1m, 15m e 1h. | Time Window Engine + Aggregator Strategy | Rafael Castro |
| **S5.3 — Gerador de Mapa de Calor** | Projeção de pixels $(u, v)$ no plano de mundo pela homografia I3 ($H \in \mathbb{R}^{3\times 3}$) e cálculo de densidade em grade. | Spatial Coordinate Converter + Grid Density Calculator | Rafael Castro |
| **S5.4 — Time-Series Store (DuckDB)** | Armazenamento colunar OLAP, worker de rollup (1s → 1m → 15m → 1h) e consultas SQL de séries temporais. | DuckDB Repository + Downsampling Rollup Worker | Rafael Castro |

---

## 🔄 Fluxo de Dados

```text
Barramento B3 (envelope JSON)
  └─> B3EventConsumer.subscribe(topic, handler)                    (S5.1)
        └─> IngestEventUseCase.execute(envelope)
              parsing → NormalizedEvent
              DebounceHysteresisFilterStrategy.should_accept()  → descarta ruído
  └─> AggregateDwellTimeUseCase.execute(events, zone_id, t)        (S5.2)
        MovingWindowGenerator → janelas [t-1m, t], [t-15m, t], [t-1h, t]
        DwellTimeAggregationStrategy → OccupancyMetric por janela
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

**Entrada:** envelope JSON do Barramento B3:

```json
{
  "event_type": "enter",
  "origin": "track-42",
  "coords": { "x": 3.2, "y": 7.5 },
  "timestamp": "2026-10-09T14:30:00"
}
```

**Processamento:**
- `IngestEventUseCase` converte o envelope em `NormalizedEvent`. Se faltar um campo obrigatório, lança `MalformedEventEnvelopeError`.
- `DebounceHysteresisFilterStrategy(min_interval_seconds)` rejeita eventos da mesma `origin` que chegam antes do intervalo mínimo. Isso suprime rajadas (debounce) e a oscilação de detecção na borda de uma zona (histerese).

**Saída:** `NormalizedEvent`, ou `None` quando o evento é filtrado.

O `InMemoryB3EventConsumer` implementa o contrato `B3EventConsumer` sem broker real. Ele serve para desenvolvimento e testes e é o ponto de troca por um cliente Pub/Sub de verdade. O contrato espelha o consumidor usado no S4 (C++).

## 📊 S5.2 — Motor de Agregação

**Entrada:** lista de `NormalizedEvent` de uma zona e um instante de referência.

**Processamento** (`DwellTimeAggregationStrategy`):
- **Dwell time médio:** pareia eventos `enter`/`exit` em ordem cronológica e calcula a média das durações.
- **Pico de ocupação:** percorre a linha do tempo (+1 em cada entrada, −1 em cada saída) e guarda o máximo simultâneo.
- **Contagem total:** número de eventos `enter` na janela.

As janelas padrão são **1m, 15m e 1h**, gravadas com as granularidades `"1m"`, `"15m"` e `"1h"`.

**Saída:** `OccupancyMetricDTO { zone_id, dwell_time_avg, occupancy_peak, total_count }` por janela.

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
| `occupancy_metrics` | `zone_id`, `granularity`, `start_time`, `end_time`, `dwell_time_avg`, `occupancy_peak`, `total_count` |
| `heatmap_cells` | `grid_id`, `timestamp`, `x`, `y`, `density` |

**Rollup:** `DownsamplingRollupWorker.run(zone_id, reference_time)` encadeia `1s → 1m → 15m → 1h`. Ele deve ser disparado por um cron externo. Em cada salto, `DownsamplingService` consolida as métricas finas assim:
- `total_count`: soma;
- `occupancy_peak`: máximo;
- `dwell_time_avg`: média **ponderada** por `total_count`.

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

O módulo expõe o router, mas ainda **não tem um ponto de entrada (`main.py`)**. Para servir a API localmente:

```python
# app.py
from fastapi import FastAPI

from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.presentation.http.metrics_query_controller import create_metrics_query_router

repository = DuckDBTimeSeriesRepository("s5_metrics.db")  # ou ":memory:"
app = FastAPI(title="S5 — Métricas e Séries Temporais")
app.include_router(create_metrics_query_router(repository))
```

```bash
uvicorn app:app --reload
# http://localhost:8000/docs
```

---

## ✅ Validação

| Verificação | Resultado |
| :--- | :--- |
| `pytest` (unitários + integração) | 59/59 aprovados |
| Invariantes de domínio | Coordenadas não finitas, janelas invertidas, densidades negativas, matrizes fora de 3×3 e IDs vazios lançam exceções específicas de `DomainError` |
| Persistência DuckDB | Escrita e consulta por zona, granularidade e intervalo de tempo |
| API HTTP | Rotas `/api/v5/metrics` e `/api/v5/heatmaps` testadas via `TestClient` |
