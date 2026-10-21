# S5 — Métricas e Séries Temporais (Metrics & Time Series)

> Componente da **Camada 3 (Serviço)** do Squad **MOD-2** (Mídia, Métricas e Interfaces) no projeto **ODS 2026/2**.

O serviço **S5** transforma o que o S1 e o S2 publicam (arquitetura 6c, Especificação de interfaces 1.0) em dados agregados **no tempo** (tempo de permanência, ocupação, entradas, eventos por tipo) e **no espaço** (segundos de presença por célula, em metros quando a câmera tem calibração do I3 e em pixels quando não tem). As métricas são persistidas em um armazenamento analítico colunar (**DuckDB**), publicadas no barramento B3 ao fechar cada janela e consultadas pelas aplicações por request/reply (`ods.s5.metrics.query` e `ods.s5.heatmap.query`).

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
│   │   ├── entities/           # ZoneTransition, ZoneOccupancySample, PositionSample, QualifiedEvent,
│   │   │                       #   SessionStart, ReplayState, OccupancyMetric, EventMetric, HeatmapGrid
│   │   ├── value_objects/      # Envelope, TimeWindow, WorldCoordinate, PixelCoordinate,
│   │   │                       #   SpatialCell, HomographyMatrix
│   │   ├── repositories/       # Contrato ITimeSeriesRepository
│   │   ├── services/           # MessageDeduplicator, AggregationStrategy, PresenceAccumulator,
│   │   │                       #   MovingWindowGenerator, SpatialCoordinateConverter,
│   │   │                       #   GridDensityCalculator, DownsamplingService
│   │   └── exceptions/         # Hierarquia de exceções (DomainError, ApplicationError)
│   ├── application/            # 2. Orquestração de casos de uso e DTOs
│   │   ├── use_cases/          # IngestEnvelope, HandleBusMessage, CloseMetricWindows,
│   │   │                       #   AnswerQuery, QueryMetrics, QueryHeatmap,
│   │   │                       #   AggregateZoneMetrics, GenerateHeatmap, RollupMetrics
│   │   ├── parsers/            # Leitura do envelope comum de 13 campos
│   │   ├── messaging/          # Envelopes EV-SERVIÇO e RPL e payloads das métricas
│   │   ├── ports/              # IEventPublisher (publicação no B3)
│   │   ├── state/              # MetricsBuffer (mensagens das janelas abertas)
│   │   └── dtos/               # OccupancyMetricDTO, HeatmapQueryDTO
│   ├── infrastructure/         # 3. Adaptadores e integrações externas
│   │   ├── b3_bus/             # Consumidor/publicador do B3 (contrato + in-memory) e assinaturas do S5
│   │   ├── database/           # DuckDBTimeSeriesRepository
│   │   ├── i3_calibration/     # Carregador da matriz de homografia (JSON)
│   │   └── workers/            # MetricsWindowWorker, DownsamplingRollupWorker
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
| **S5.1 — Ingestor de Eventos B3** | Consumo Pub/Sub do B3, leitura do envelope comum, deduplicação por `message_id` e conversão de `ods.s1.zone_transition`, `ods.s1.zone_occupancy`, `ods.s1.position`, `ods.s2.event`, `ods.session.started` e `ods.p6.replay.state`; reinício do estado a cada sessão. | Event Consumer + Deduplicator | Rafael Castro |
| **S5.2 — Motor de Agregação** | Métricas por zona (permanência, pico e média de ocupação, entradas) e por tipo de evento em janelas alinhadas de 1m, 15m, 1h e 1d, publicadas em `ods.s5.zone_metrics` e `ods.s5.event_metrics`. | Time Window Engine + Aggregator Strategy | Rafael Castro |
| **S5.3 — Mapa de Calor e Consultas** | Segundos de presença por célula a partir de `ods.s1.position`; respostas a `ods.s5.metrics.query` e `ods.s5.heatmap.query`. | Presence Accumulator + Request/Reply | Rafael Castro |
| **S5.4 — Time-Series Store (DuckDB)** | Armazenamento colunar OLAP, worker de rollup (1s → 1m → 15m → 1h) e consultas SQL de séries temporais. | DuckDB Repository + Downsampling Rollup Worker | Rafael Castro |

---

## 🔄 Fluxo de Dados

```text
Barramento B3 (ods.s1.zone_transition, ods.s1.zone_occupancy, ods.s2.event,
              ods.session.started, ods.p6.replay.state)
  └─> subscribe_s5(consumer, handler) — um tópico por schema        (S5.1)
        └─> HandleBusMessageUseCase.execute(message)
              IngestEnvelopeUseCase → Envelope + ZoneTransition | ZoneOccupancySample | QualifiedEvent
              MessageDeduplicator → descarta message_id repetido
              MetricsBuffer.add → guarda até a janela fechar; nova sessão reinicia o estado
  └─> MetricsWindowWorker.run() → CloseMetricWindowsUseCase.execute(now)  (S5.2)
        closed_windows → janelas alinhadas 1m, 15m, 1h, 1d que fecharam
        ZoneOccupancyAggregationStrategy → OccupancyMetric por zona
        EventMetricsAggregation → EventMetric por tipo de evento
        persiste e publica ods.s5.zone_metrics / ods.s5.event_metrics
        PresenceAccumulator.drain → presença dos minutos fechados
  └─> ods.s1.position → PresenceAccumulator.observe                (S5.3)
        segundos por célula fina (0,1 m ou 10 px) e minuto
  └─> ods.s5.metrics.query / ods.s5.heatmap.query → AnswerQueryUseCase  (S5.3)
        QueryMetricsUseCase · QueryHeatmapUseCase → reply em ods.s5.*.reply
  └─> DuckDBTimeSeriesRepository                                   (S5.4)
        tabelas occupancy_metrics / event_metrics / presence_cells
  └─> GET /api/v5/metrics/{zone_id} · GET /api/v5/heatmaps/{grid_id}   (depuração)
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
- Schema fora de `ods.s1.zone_transition`, `ods.s1.zone_occupancy`, `ods.s2.event`, `ods.session.started` e `ods.p6.replay.state` → `UnsupportedSchemaError`.
- `parse_envelope` exige os seis campos fixos e os do perfil do schema: EV-SINAL nas mensagens do S1 (`captured_at`, `source_id`, `session_id`, `sequence`, `artifact_version`) e EV-SERVIÇO no `ods.s2.event` (`captured_at`, `session_id`, `sequence`). `ods.session.started` e `ods.p6.replay.state` usam EV-SINAL sem `artifact_version`; `source_id` não é exigido neles porque P6 reproduz várias fontes, listadas em `sources`. Marcos de tempo precisam de fuso (`Z`) e são convertidos para UTC sem `tzinfo`, convenção de todo o S5. Campo ausente ou com formato inválido → `MalformedEventEnvelopeError`.
- `MessageDeduplicator` descarta mensagens cujo `message_id` já foi aceito (regra 7) e retorna `None`. O id só é registrado depois que a mensagem é aceita.
- `schema_version` com MAJOR diferente de `1` → `UnsupportedSchemaVersionError`; qualquer MINOR do MAJOR 1 é aceito (regra 8).

Não há debounce nem histerese no S5: na 6c, a histerese é do S1, configurada pelo artefato ZONES, e a transição já chega confirmada.

**Saída:** `IngestedMessage` com o envelope e um `ZoneTransition`, `ZoneOccupancySample` ou `QualifiedEvent`, ou `None` quando a mensagem é repetida. `subscribe_s5` assina um tópico por schema; uma mensagem fora do contrato é registrada em log e descartada, sem interromper as seguintes.

**Sessões** (`MetricsBuffer`): a camada 3 reinicia o estado a cada `ods.session.started` (Especificação 1.0, seção 7).
- Uma sessão nova descarta as transições, amostras e eventos da anterior. Mensagens atrasadas da sessão encerrada, ou da `previous_session_id` anunciada, são ignoradas.
- Os tópicos são independentes, então mensagens do S1 e do S2 podem chegar antes do anúncio da sessão. Nesse caso a sessão é adotada como `LIVE`, com início no primeiro `captured_at` recebido. O anúncio, quando chega, só completa o modo e o início, sem descartar o que já foi recebido.
- `ods.p6.replay.state` não vira métrica: ele só faz andar o relógio de captura da sessão de replay.

O `InMemoryB3EventConsumer` implementa os contratos `B3EventConsumer` e `IEventPublisher` sem broker real: o que é publicado é entregue aos handlers do mesmo processo. Ele serve para desenvolvimento e testes e é o ponto de troca por um cliente Pub/Sub de verdade. O contrato espelha o consumidor usado no S4 (C++).

## 📊 S5.2 — Motor de Agregação e publicação

**Entrada:** o `MetricsBuffer`, alimentado pelo S5.1 com as transições, as amostras de ocupação e os eventos qualificados ainda dentro de uma janela aberta.

**Disparo:** `MetricsWindowWorker.run()`, chamado por um agendador externo em intervalo menor que a menor janela (ex.: a cada 5 s). Cada disparo fecha as janelas **alinhadas ao relógio UTC** (14:00–14:15, não t−15m–t) de **1m, 15m, 1h e 1d** que terminaram desde o disparo anterior. Disparos extras não publicam nada. Alguns detalhes:
- uma janela só fecha 2 s depois do seu fim, para acolher a latência entre captura e publicação;
- janelas perdidas entre dois disparos são fechadas todas, em ordem;
- a cada sessão nova o cursor volta ao início dela, e as janelas ainda abertas da sessão anterior são abandonadas.

**Relógio:** em sessão `LIVE`, o relógio é o de parede. Em `REPLAY`, é o maior `captured_at` recebido na sessão: o tempo de captura reproduzido é o da gravação, que não acompanha a parede e volta em `SEEK` e `LOOP`. P6 publica `ods.p6.replay.state` a cada 1 s em reprodução, o que mantém esse relógio andando mesmo quando nenhuma zona muda. Com o replay pausado, nenhuma janela fecha.

**Métricas por zona** (`ZoneOccupancyAggregationStrategy`), em janelas semiabertas `[início, fim)`, para cada zona já vista em mensagens do S1:
- **Dwell time médio:** média do `dwell_s` das transições `EXIT` na janela.
- **Contagem total:** número de transições `ENTER` na janela.
- **Pico de ocupação:** maior `count` vigente na janela.
- **Ocupação média:** `count` médio ponderado pelo tempo em que cada amostra vigorou. A contagem no início da janela é a da última amostra anterior a ela; sem amostra anterior, a zona é considerada vazia.

**Métricas por tipo de evento** (`EventMetricsAggregation`), uma por `(event_type, zone_id, class)` com ocorrência:
- `count`: eventos distintos (`event_id`) cujo `started_at` cai na janela;
- `uncertain_count`: desses, os que estavam `UNCERTAIN` na última publicação anterior ao fim da janela;
- `duration_avg_ms`: média do `duration_ms` dos eventos `ENDED` na janela.

**Saída:** cada métrica é persistida no DuckDB e publicada com o envelope EV-SERVIÇO (`producer: "S5"`, `captured_at` = fim da janela, `sequence` por sessão). `source_id` e `artifact_version` (versão de ZONES) vêm das últimas mensagens do S1 da zona; em `event_metrics`, `artifact_version` é a versão das regras do S2. Exemplo de `ods.s5.zone_metrics`:

```json
{
  "message_type": "event", "schema": "ods.s5.zone_metrics", "schema_version": "1.0", "producer": "S5",
  "captured_at": "2026-09-23T14:15:00.000Z", "source_id": "cam0", "artifact_version": "zones-a8-2",
  "payload": {
    "zone_id": "vaga-12",
    "window_start_at": "2026-09-23T14:00:00.000Z", "window_end_at": "2026-09-23T14:15:00.000Z",
    "granularity": "15m",
    "total_count": 3, "occupancy_peak": 1, "occupancy_avg": 0.72, "dwell_avg_s": 1830
  }
}
```

O `MetricsBuffer` descarta o que ficou mais de um dia antes da última janela fechada. Ele preserva a última amostra de ocupação de cada zona e os eventos do S2 ainda não encerrados.

O `AggregateZoneMetricsUseCase`, com janelas móveis terminando em um instante de referência, continua disponível para cálculo sob demanda.

## 🗺️ S5.3 — Mapa de Calor e Consultas

### Presença por célula

**Entrada:** `ods.s1.position`, uma mensagem por quadro e câmera, com `point_px` de cada rastro e, quando a câmera tem calibração do I3, `position_m` e `space_id`. O S5 não aplica homografia: a posição em metros já vem do S1.

**Processamento** (`PresenceAccumulator`):
- O intervalo entre duas posições consecutivas do mesmo rastro conta como presença na célula da primeira, que é onde o objeto estava naquele tempo.
- Intervalos acima de 1 s são descartados: houve perda de quadros, e o objeto pode não ter ficado ali.
- A presença é somada por espaço (`space_id` em metros, ou `source_id` em pixels), classe, célula fina (**0,1 m** ou **10 px**) e minuto UTC.
- Os minutos fechados são gravados na tabela `presence_cells` a cada disparo do `MetricsWindowWorker`, com o `mode` da sessão.
- Câmeras diferentes acumulam separadamente. Uma pessoa vista por duas câmeras calibradas no mesmo espaço conta em dobro; a fusão entre câmeras é do S2.

### `ods.s5.heatmap.query`

Consulta com `space_id` + `cell_size_m`, ou `source_id` + `cell_size_px` em instalação sem calibração. `class` é opcional.

```json
{ "space_id": "patio-1", "class": "person", "period_start_at": "2026-09-23T14:00:00.000Z",
  "period_end_at": "2026-09-23T15:00:00.000Z", "cell_size_m": 0.5 }
```

- As células finas são agrupadas no tamanho pedido, que precisa ser pelo menos a resolução base.
- A grade cobre só o retângulo com presença: `origin` é o canto da primeira célula, e `cells[y][x]` são segundos de presença, inteiros.
- Sem presença no período, a reply traz uma grade vazia.
- Grade maior que 200×200 → `GRID_TOO_LARGE`. A especificação prevê entregá-la por `heatmap_uri`, mas o S5 ainda não tem onde guardar o arquivo.

### `ods.s5.metrics.query`

```json
{ "metric": "ZONE", "zone_id": "vaga-12", "class": "vehicle",
  "period_start_at": "2026-09-22T00:00:00.000Z", "period_end_at": "2026-09-23T00:00:00.000Z",
  "granularity": "1h" }
```

- `metric` `ZONE` devolve itens no formato de `ods.s5.zone_metrics`; `EVENT` devolve no formato de `ods.s5.event_metrics`, filtrando por `event_type`, `zone_id` e `class`, todos opcionais.
- Em `ZONE`, `class` é aceito mas não restringe a série. As métricas por zona somam as classes que a zona conta, definidas no artefato ZONES, e os itens saem sem o campo `class`.
- A série vem em ordem cronológica, com no máximo 1000 pontos. Período com mais de 1000 janelas da granularidade pedida → `PERIOD_TOO_LONG`.
- Zona sem nenhuma métrica gravada → `UNKNOWN_ZONE`. Campo ausente ou inválido → `INVALID_QUERY`.

### Respostas (`AnswerQueryUseCase`)

- A consulta segue o perfil CMD (`target` obrigatório). Consulta para outro `target` é ignorada.
- A reply sai em `ods.s5.metrics.reply` ou `ods.s5.heatmap.reply`, com o perfil RPL: `correlation_id` é o `message_id` da consulta, e o payload traz `status` `OK`, ou `ERROR` com `error {code, message}`.
- Consultas não alteram estado, então uma consulta repetida é respondida de novo, em vez de descartada.
- As consultas leem só métricas `LIVE`.

### Código anterior à 6c

`GenerateHeatmapUseCase`, `GridDensityCalculator`, `HomographyCalibratorAdapter` e a tabela `heatmap_cells` são do fluxo anterior, que aplicava a homografia no próprio S5 e normalizava a densidade entre 0 e 1. Continuam no código apenas para a rota REST de depuração.

## 🗄️ S5.4 — Time-Series Store (DuckDB)

**Tabelas:**

| Tabela | Colunas |
| :--- | :--- |
| `occupancy_metrics` | `zone_id`, `granularity`, `start_time`, `end_time`, `dwell_time_avg`, `occupancy_peak`, `total_count`, `occupancy_avg`, `mode`, `session_id` |
| `event_metrics` | `event_type`, `zone_id`, `object_class`, `granularity`, `start_time`, `end_time`, `count`, `uncertain_count`, `duration_avg_ms`, `mode`, `session_id` |
| `presence_cells` | `mode`, `session_id`, `space_kind`, `space_key`, `object_class`, `cell_x`, `cell_y`, `bucket_start`, `seconds` |
| `heatmap_cells` | `grid_id`, `timestamp`, `x`, `y`, `density` (fluxo anterior à 6c) |

**Rollup:** `DownsamplingRollupWorker.run(zone_id, reference_time)` encadeia `1s → 1m → 15m → 1h`. Ele deve ser disparado por um cron externo. Em cada salto, `DownsamplingService` consolida as métricas finas assim:
- `total_count`: soma;
- `occupancy_peak`: máximo;
- `dwell_time_avg`: média **ponderada** por `total_count`;
- `occupancy_avg`: média ponderada pela duração de cada janela fina.

Cada métrica é gravada com o `mode` (`LIVE` ou `REPLAY`) e o `session_id` que a produziram. Um replay reproduz o tempo de captura original, então as janelas dele coincidem com as da captura ao vivo daquele dia. Por isso as consultas leem só `LIVE`, salvo pedido explícito (`mode="REPLAY"`), e um replay não duplica o histórico.

Bancos criados antes de `occupancy_avg`, `mode` e `session_id` existirem recebem as colunas na abertura, com `0` e `LIVE` nas linhas já gravadas.

**API REST de depuração** (`create_metrics_query_router(repository)`, prefixo `/api/v5`). As aplicações consultam o S5 pelo barramento (S5.3); a API serve para inspecionar o banco durante o desenvolvimento:

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
| `pytest` (unitários + integração) | 196/196 aprovados |
| Invariantes de domínio | Coordenadas não finitas, janelas invertidas, densidades negativas, matrizes fora de 3×3, IDs vazios, envelopes fora do contrato e `EXIT` sem `dwell_s` lançam exceções específicas de `DomainError` |
| Contrato de entrada | Exemplos de `ods.s1.zone_transition`, `ods.s1.zone_occupancy` e `ods.s2.event` da Especificação 1.0, deduplicação por `message_id` e regra de MAJOR.MINOR |
| Contrato de saída | `ods.s5.zone_metrics` e `ods.s5.event_metrics` com envelope EV-SERVIÇO; fluxo de ponta a ponta pelo barramento em memória |
| Sessão e replay | Reinício do estado por `ods.session.started`, relógio de captura em replay, pausa, `LOOP` com nova sessão e separação LIVE/REPLAY no DuckDB |
| Consultas | `ods.s5.metrics.query` e `ods.s5.heatmap.query` com os exemplos da especificação, códigos de erro, reply RPL e ciclo completo pelo barramento em memória |
| Persistência DuckDB | Escrita e consulta por zona, granularidade e intervalo de tempo |
| API HTTP | Rotas `/api/v5/metrics` e `/api/v5/heatmaps` testadas via `TestClient` |
