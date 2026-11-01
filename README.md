# S5 — Métricas e Séries Temporais (Metrics & Time Series)

> Componente da **Camada 3 (Serviço)** do Squad **MOD-2** (Mídia, Métricas e Interfaces) no projeto **ODS 2026/2**.

O serviço **S5** transforma o que o S1 e o S2 publicam (arquitetura 6c, Especificação de interfaces 1.0) em dados agregados **no tempo** (tempo de permanência, ocupação, entradas, eventos por tipo) e **no espaço** (segundos de presença por célula, em metros quando a câmera tem calibração do I3 e em pixels quando não tem). As métricas são persistidas em um armazenamento analítico colunar (**DuckDB**), publicadas no barramento B3 ao fechar cada janela e consultadas pelas aplicações por request/reply (`ods.s5.metrics.query` e `ods.s5.heatmap.query`).

---

## 🏗️ Arquitetura e Estrutura de Diretórios

O projeto adota os princípios de **Clean Architecture**, **Domain-Driven Design (DDD)** e **Design Patterns (GoF)**, desenvolvido em **Python 3.12**.

```text
s5/
├── README.md                   # Documentação do componente
├── app.py                      # Ponto de entrada do serviço (uvicorn app:app)
├── seed.py                     # Dados de exemplo para a API de depuração
├── requirements.txt            # Dependências de execução, com versões fixadas
├── requirements-dev.txt        # Dependências dos testes
├── Dockerfile                  # Imagem do serviço
├── docker-compose.yml          # Sobe o serviço com um volume para o banco
├── scripts/                    # Teste curto da consulta em um broker Kafka
├── pytest.ini                  # Configuração dos testes (pythonpath = .)
├── contracts/                  # JSON Schemas e exemplos das mensagens do S5
├── src/
│   ├── domain/                 # 1. Coração do negócio (zero dependências externas)
│   │   ├── entities/           # ZoneTransition, ZoneOccupancySample, PositionSample, QualifiedEvent,
│   │   │                       #   SessionStart, ReplayState, OccupancyMetric, EventMetric
│   │   ├── value_objects/      # Envelope, TimeWindow, granularidades, janelas alinhadas,
│   │   │                       #   RetentionPolicy
│   │   ├── repositories/       # Contrato ITimeSeriesRepository
│   │   ├── services/           # MessageDeduplicator, AggregationStrategy, EventMetricsAggregation,
│   │   │                       #   PresenceAccumulator
│   │   └── exceptions/         # Hierarquia de exceções (DomainError, ApplicationError)
│   ├── application/            # 2. Orquestração de casos de uso
│   │   ├── use_cases/          # IngestEnvelope, HandleBusMessage, CloseMetricWindows,
│   │   │                       #   AnswerQuery, QueryMetrics, QueryHeatmap, PurgeExpiredData
│   │   ├── parsers/            # Leitura do envelope comum de 13 campos
│   │   ├── messaging/          # Envelopes EV-SERVIÇO e RPL e payloads das métricas
│   │   ├── ports/              # IEventPublisher (publicação no B3)
│   │   └── state/              # MetricsBuffer (mensagens das janelas abertas e sessão)
│   ├── infrastructure/         # 3. Adaptadores e integrações externas
│   │   ├── b3_bus/             # Barramento B3: Kafka, em memória e assinaturas do S5
│   │   ├── contracts/          # ContractValidator e ValidatingPublisher
│   │   ├── database/           # DuckDBTimeSeriesRepository
│   │   └── workers/            # MetricsWindowWorker
│   ├── presentation/           # 4. Exposição de API
│   │   └── http/               # Router FastAPI de depuração (/api/v5)
│   └── composition.py          # Monta o S5 completo sobre um barramento e um repositório
└── tests/
    ├── fixtures/               # Mensagens de exemplo da Especificação 1.0
    ├── contract/               # Exemplos de contracts/ contra os schemas
    ├── unit/                   # Domínio e casos de uso (com fakes em memória)
    └── integration/            # DuckDB real, HTTP (TestClient), B3 in-memory, composição
```

A regra de dependência é estrita: `domain` não importa nada de fora; `application` só conhece `domain`; `infrastructure` e `presentation` implementam os contratos definidos no domínio e na aplicação. `composition.py` é a raiz de composição: fica fora das camadas porque conhece todas elas.

---

## 🧩 Submódulos e Responsabilidades (Squad MOD-2)

Conforme definido em [`docs/responsability.md`](../docs/responsability.md):

| Submódulo | Funcionalidade | Padrão / Arquitetura | Responsável |
| :--- | :--- | :--- | :--- |
| **S5.1 — Ingestor de Eventos B3** | Consumo Pub/Sub do B3, leitura do envelope comum, deduplicação por `message_id` e conversão de `ods.s1.zone_transition`, `ods.s1.zone_occupancy`, `ods.s1.position`, `ods.s2.event`, `ods.session.started` e `ods.p6.replay.state`; reinício do estado a cada sessão. | Event Consumer + Deduplicator | Rafael Castro |
| **S5.2 — Motor de Agregação** | Métricas por zona (permanência, pico e média de ocupação, entradas) e por tipo de evento em janelas alinhadas de 1m, 15m, 1h e 1d, publicadas em `ods.s5.zone_metrics` e `ods.s5.event_metrics`. | Time Window Engine + Aggregator Strategy | Rafael Castro |
| **S5.3 — Mapa de Calor e Consultas** | Segundos de presença por célula a partir de `ods.s1.position`; respostas a `ods.s5.metrics.query` e `ods.s5.heatmap.query`. | Presence Accumulator + Request/Reply | Rafael Castro |
| **S5.4 — Time-Series Store (DuckDB)** | Armazenamento colunar das métricas e da presença, separado por modo LIVE/REPLAY, e consultas SQL de séries temporais. | DuckDB Repository | Rafael Castro |

---

## 🔄 Fluxo de Dados

```text
Barramento B3 (ods.s1.zone_transition, ods.s1.zone_occupancy, ods.s1.position,
              ods.s2.event, ods.session.started, ods.p6.replay.state)
  └─> subscribe_s5(consumer, handler) — um tópico por schema        (S5.1)
        └─> HandleBusMessageUseCase.execute(message)
              IngestEnvelopeUseCase → Envelope + objeto de domínio do schema
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
  └─> GET /api/v5/metrics · GET /api/v5/heatmap                    (depuração)
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
- Schema fora de `ods.s1.zone_transition`, `ods.s1.zone_occupancy`, `ods.s1.position`, `ods.s2.event`, `ods.session.started` e `ods.p6.replay.state` → `UnsupportedSchemaError`.
- `parse_envelope` exige os seis campos fixos e os do perfil do schema: EV-SINAL nas mensagens do S1 (`captured_at`, `source_id`, `session_id`, `sequence`, `artifact_version`) e EV-SERVIÇO no `ods.s2.event` (`captured_at`, `session_id`, `sequence`). `ods.session.started` e `ods.p6.replay.state` usam EV-SINAL sem `artifact_version`; `source_id` não é exigido neles porque P6 reproduz várias fontes, listadas em `sources`. Marcos de tempo precisam de fuso (`Z`) e são convertidos para UTC sem `tzinfo`, convenção de todo o S5. Campo ausente ou com formato inválido → `MalformedEventEnvelopeError`.
- `MessageDeduplicator` descarta mensagens cujo `message_id` já foi aceito (regra 7) e retorna `None`. O id só é registrado depois que a mensagem é aceita.
- `schema_version` com MAJOR diferente de `1` → `UnsupportedSchemaVersionError`; qualquer MINOR do MAJOR 1 é aceito (regra 8).

Não há debounce nem histerese no S5: na 6c, a histerese é do S1, configurada pelo artefato ZONES, e a transição já chega confirmada.

**Saída:** `IngestedMessage` com o envelope e um `ZoneTransition`, `ZoneOccupancySample`, `PositionSample`, `QualifiedEvent`, `SessionStart` ou `ReplayState`, ou `None` quando a mensagem é repetida. `subscribe_s5` assina um tópico por schema; uma mensagem fora do contrato é registrada em log e descartada, sem interromper as seguintes.

**Sessões** (`MetricsBuffer`): a camada 3 reinicia o estado a cada `ods.session.started` (Especificação 1.0, seção 7).
- Uma sessão nova descarta as transições, amostras e eventos da anterior. Mensagens atrasadas da sessão encerrada, ou da `previous_session_id` anunciada, são ignoradas.
- Os tópicos são independentes, então mensagens do S1 e do S2 podem chegar antes do anúncio da sessão. Nesse caso a sessão é adotada como `LIVE`, com início no primeiro `captured_at` recebido. O anúncio, quando chega, só completa o modo e o início, sem descartar o que já foi recebido.
- `ods.p6.replay.state` não vira métrica: ele só faz andar o relógio de captura da sessão de replay.

**Barramento:** dois adaptadores implementam os contratos `B3EventConsumer` e `IEventPublisher`.

- `KafkaB3Bus` (`confluent-kafka`) segue o Guia de Uso do Kafka: um tópico por schema, `group.id` próprio, poll de 1 s e endereço do broker sempre vindo de configuração. Mensagem que não é JSON de um objeto é descartada e registrada no log. Erro em um handler não interrompe a leitura.
- `InMemoryB3EventConsumer` entrega o que é publicado aos handlers do mesmo processo. Serve para desenvolvimento e testes.

Sem posição salva, o grupo Kafka começa em `latest`: o S5 acompanha o presente, e ler o histórico inteiro responderia a consultas antigas e recalcularia métricas de sessões encerradas. As mensagens chegam em uma thread própria; um lock protege o buffer contra o fechamento de janelas, e o repositório usa um cursor DuckDB por thread.

## 📊 S5.2 — Motor de Agregação e publicação

**Entrada:** o `MetricsBuffer`, alimentado pelo S5.1 com as transições, as amostras de ocupação e os eventos qualificados ainda dentro de uma janela aberta.

**Disparo:** `MetricsWindowWorker.run()`, chamado por um agendador externo em intervalo menor que a menor janela (ex.: a cada 5 s). Cada disparo fecha as janelas **alinhadas ao relógio UTC** (14:00–14:15, não t−15m–t) de **1m, 15m, 1h e 1d** que terminaram desde o disparo anterior. Disparos extras não publicam nada. Alguns detalhes:
- uma janela só fecha 2 s depois do seu fim, para acolher a latência entre captura e publicação;
- janelas perdidas entre dois disparos são fechadas em ordem. Em sessão `LIVE`, a recuperação vai no máximo 1 hora para trás, para não publicar milhares de janelas de uma vez depois de uma parada longa;
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

O `MetricsBuffer` descarta o que ficou mais de um dia antes da última janela fechada. Ele preserva a última amostra de ocupação de cada zona, que é a contagem vigente no início da próxima janela. Um evento do S2 fica inteiro enquanto alguma publicação dele for recente; quando nem a última é, ele sai, tenha ou não recebido `ENDED`.

Antes de publicar, toda mensagem passa pelo validador de contratos (`ValidatingPublisher`, schemas em [`contracts/`](contracts/README.md)). Mensagem fora do contrato não chega ao barramento: é descartada e registrada no log de erro.

Cada granularidade é calculada direto dos dados brutos do buffer, sem rollup de uma granularidade fina para outra: assim a média de permanência de 1h, por exemplo, é a média das saídas da hora, e não a média das médias de cada minuto.

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

- As células finas são agrupadas no tamanho pedido, que precisa ser múltiplo da resolução base (ex.: 0,5 m ou 20 px). Outro tamanho → `INVALID_QUERY`.
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

## 🗄️ S5.4 — Time-Series Store (DuckDB)

**Tabelas:**

| Tabela | Colunas |
| :--- | :--- |
| `occupancy_metrics` | `zone_id`, `granularity`, `start_time`, `end_time`, `dwell_time_avg`, `occupancy_peak`, `total_count`, `occupancy_avg`, `mode`, `session_id`, `stored_at` |
| `event_metrics` | `event_type`, `zone_id`, `object_class`, `granularity`, `start_time`, `end_time`, `count`, `uncertain_count`, `duration_avg_ms`, `mode`, `session_id`, `stored_at` |
| `presence_cells` | `mode`, `session_id`, `space_kind`, `space_key`, `object_class`, `cell_x`, `cell_y`, `bucket_start`, `seconds`, `stored_at` |

Os nomes de coluna são internos. Para fora, por barramento ou pela API de depuração, as métricas saem sempre com os campos da Especificação 1.0 (`dwell_avg_s`, `window_start_at` etc.).

Cada métrica é gravada com o `mode` (`LIVE` ou `REPLAY`) e o `session_id` que a produziram. Um replay reproduz o tempo de captura original, então as janelas dele coincidem com as da captura ao vivo daquele dia. Por isso as consultas leem só `LIVE`, e um replay não duplica o histórico.

Toda linha guarda também `stored_at`, o instante UTC em que foi gravada.

**Retenção** (`RetentionPolicy`, `PurgeExpiredDataUseCase`): o expurgo roda a cada `S5_PURGE_SECONDS` (padrão 3600) e apaga o que passou do prazo.

| Dado | Expira pelo | Prazo padrão |
| :--- | :--- | :--- |
| Métricas LIVE de 1m | fim da janela | 7 dias |
| Métricas LIVE de 15m | fim da janela | 90 dias |
| Métricas LIVE de 1h | fim da janela | 365 dias |
| Métricas LIVE de 1d | fim da janela | 1825 dias |
| Presença LIVE por célula | fim do minuto | 14 dias |
| Tudo o que veio de replay | `stored_at` | 7 dias |

Dados de replay expiram pelo momento em que foram gravados, porque o tempo de captura deles é o da gravação reproduzida, que pode ser de dias atrás. Os prazos são provisórios, até o orçamento de disco da Jetson ser fechado com o SIS-1 (P3).

Bancos criados antes de `occupancy_avg`, `mode`, `session_id` e `stored_at` existirem recebem as colunas na abertura: `0` em `occupancy_avg`, `LIVE` em `mode` e o instante da migração em `stored_at`.

**API REST de depuração** (`create_metrics_query_router(repository)`, prefixo `/api/v5`). As aplicações consultam o S5 pelo barramento (S5.3). A API executa os mesmos casos de uso das consultas, com os mesmos parâmetros (como query string), o mesmo formato de resposta e os mesmos códigos de erro, para inspecionar o banco durante o desenvolvimento:

| Método | Rota | Equivale a | Erros |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v5/metrics` | `ods.s5.metrics.query` | `404` em `UNKNOWN_ZONE`; `400` nos demais |
| `GET` | `/api/v5/heatmap` | `ods.s5.heatmap.query` | `400` |

---

## 🚀 Como Executar

### Instalação

```bash
cd s5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Docker

```bash
S5_KAFKA_BROKERS=<host:porta> docker compose up -d --build
```

O endereço do broker não tem valor padrão de propósito: sem `S5_KAFKA_BROKERS`, o S5 sobe com o barramento em memória. A imagem foi testada em amd64; a execução na Jetson (arm64) ainda não foi verificada.

### Testes

```bash
pytest                # suíte completa
pytest tests/unit     # somente testes unitários
pytest tests/contract # somente os exemplos de contracts/
```

O teste contra um broker Kafka real só roda com `S5_TEST_KAFKA_BROKERS` definido. Ele cria tópicos e publica mensagens, então use um broker local descartável, nunca o do projeto:

```bash
docker run -d --rm --name s5-kafka-teste -p 127.0.0.1:9092:9092 apache/kafka:3.9.0
S5_TEST_KAFKA_BROKERS=localhost:9092 pytest tests/integration/test_kafka_b3_bus_real.py
docker stop s5-kafka-teste
```

Os testes unitários usam fakes em memória ([`tests/unit/application/fakes.py`](tests/unit/application/fakes.py)). Os de integração usam DuckDB real (`:memory:`), o `TestClient` do FastAPI e o consumidor B3 em memória. Os de contrato verificam cada exemplo de [`contracts/examples/`](contracts/examples) contra o seu schema.

### Subindo a API

O ponto de entrada é [`app.py`](app.py). Ele monta o S5 completo por `build_s5` ([`composition.py`](src/composition.py)) sobre o barramento em memória e um `DuckDBTimeSeriesRepository`, fecha as janelas a cada `S5_TICK_SECONDS` (padrão 5), roda o expurgo de retenção a cada `S5_PURGE_SECONDS` (padrão 3600) e expõe a API de depuração. O barramento é escolhido por `S5_KAFKA_BROKERS`: com o endereço do broker, usa o Kafka; sem ele, usa o barramento em memória, e mensagens só chegam de dentro do processo. `S5_KAFKA_GROUP_ID` (padrão `S5-metricas`) e `S5_KAFKA_OFFSET_RESET` (padrão `latest`) ajustam o consumidor. O banco padrão é `s5_metrics.db`; para usar outro caminho (ou `:memory:`), defina `S5_DATABASE_PATH`.

```bash
uvicorn app:app --reload                                    # barramento em memória
S5_KAFKA_BROKERS=<host:porta> uvicorn app:app               # barramento Kafka
# http://localhost:8000/docs
```

O broker do projeto é pago e compartilhado pelos 15 squads. Faça testes curtos e supervisionados, e encerre o processo ao terminar. Para testar a leitura e a escrita sem publicar em tópicos de outros componentes, com o S5 rodando há pelo menos 15 s no mesmo broker:

```bash
python scripts/smoke_kafka_query.py <host:porta>
```

Para ter dados de exemplo (zona `vaga-12`, evento `PPE_NON_COMPLIANT` e presença em `patio-1`, em 2026-10-09 das 14h às 15h UTC), rode antes `python seed.py`, com o serviço parado, porque o DuckDB só aceita um processo por arquivo. Depois consulte:

```bash
P="period_start_at=2026-10-09T14:00:00.000Z&period_end_at=2026-10-09T15:00:00.000Z"
curl "http://localhost:8000/api/v5/metrics?metric=ZONE&zone_id=vaga-12&granularity=15m&$P"
curl "http://localhost:8000/api/v5/metrics?metric=EVENT&granularity=1h&$P"
curl "http://localhost:8000/api/v5/heatmap?space_id=patio-1&cell_size_m=0.5&$P"
```

---

## ✅ Validação

| Verificação | Resultado |
| :--- | :--- |
| `pytest` (unitários, integração e contrato) | 242 aprovados; 1 teste de broker real roda à parte |
| Kafka | Leitura, publicação e consulta contra Kafka 3.9 local em Docker, inclusive com o serviço rodando e janela fechada pelo relógio real. Ainda não testado no broker compartilhado do projeto |
| Invariantes de domínio | Janelas invertidas, IDs vazios, contagens negativas, enums fora do contrato, coordenadas não finitas, envelopes fora do contrato e `EXIT` sem `dwell_s` lançam exceções específicas de `DomainError` |
| Contrato de entrada | Exemplos de `ods.s1.zone_transition`, `ods.s1.zone_occupancy`, `ods.s1.position`, `ods.s2.event`, `ods.session.started` e `ods.p6.replay.state` da Especificação 1.0, deduplicação por `message_id` e regra de MAJOR.MINOR |
| Contrato de saída | `ods.s5.zone_metrics` e `ods.s5.event_metrics` com envelope EV-SERVIÇO; fluxo de ponta a ponta pelo barramento em memória |
| Sessão e replay | Reinício do estado por `ods.session.started`, relógio de captura em replay, pausa, `LOOP` com nova sessão e separação LIVE/REPLAY no DuckDB |
| Consultas | `ods.s5.metrics.query` e `ods.s5.heatmap.query` com os exemplos da especificação, códigos de erro, reply RPL e ciclo completo pelo barramento em memória |
| Persistência DuckDB | Séries por zona e por tipo de evento, presença por célula, separação LIVE/REPLAY, expurgo por prazo e migração de bancos antigos |
| Contratos | 34 exemplos válidos e inválidos dos 6 contratos do S5; tudo o que o S5 publica passa pelo validador, inclusive replies de erro |
| API HTTP | Rotas `/api/v5/metrics` e `/api/v5/heatmap` testadas via `TestClient` e com `uvicorn` sobre os dados do `seed.py` |
| Composição | S5 montado por `build_s5` ingere, publica e responde a consultas pelo barramento em memória |
