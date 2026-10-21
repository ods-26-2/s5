# Contratos do S5

JSON Schemas (draft 2020-12) das mensagens que o S5 publica ou atende, conforme a Especificação de interfaces 1.0 da arquitetura 6c. O MOD-2 é dono destes payloads (seção 6 da especificação); o envelope comum é do B1.

| Contrato | Modo | Quem envia | Quem recebe |
| :--- | :--- | :--- | :--- |
| `ods.s5.zone_metrics` | evento, perfil EV-SERVIÇO | S5 | A3, A8; opcional A4 |
| `ods.s5.event_metrics` | evento, perfil EV-SERVIÇO | S5 | A1, A3, A7, A8 |
| `ods.s5.metrics.query` | consulta, perfil CMD | A1, A3, A4, A7, A8 | S5 |
| `ods.s5.metrics.reply` | reply, perfil RPL | S5 | quem consultou |
| `ods.s5.heatmap.query` | consulta, perfil CMD | A3, A8 | S5 |
| `ods.s5.heatmap.reply` | reply, perfil RPL | S5 | quem consultou |

`s5.defs.schema.json` guarda o que os contratos compartilham: tipos (UUID, marco de tempo com milissegundos, granularidade), os perfis de envelope e os payloads de métricas, que também são os itens das séries de `ods.s5.metrics.reply`. Os perfis de envelope são a leitura do MOD-2 da seção 3 até o B1 publicar o schema oficial do envelope.

## Exemplos

`examples/<contrato>/` tem pelo menos um exemplo válido (`valid-*.json`) e um inválido (`invalid-*.json`) de cada contrato. Cada exemplo inválido erra uma coisa só, descrita no nome do arquivo. Os testes em `tests/contract/` verificam todos os exemplos a cada execução da suíte.

## Validação no publicador

O S5 confere toda mensagem contra estes schemas antes de publicar (`ValidatingPublisher`). Mensagem fora do contrato não chega ao barramento: é descartada e registrada no log de erro.

## Regras que o schema não expressa

O S5 as verifica no código:

- `uncertain_count` não excede `count` em `ods.s5.event_metrics`;
- em `ods.s5.metrics.query`, `period_start_at` é anterior a `period_end_at` e o período tem no máximo 1000 janelas da granularidade pedida;
- em `ods.s5.heatmap.query`, o tamanho da célula é múltiplo da resolução base (0,1 m ou 10 px);
- em `ods.s5.heatmap.reply`, `cells` tem `grid_height` linhas de `grid_width` células.

## Compatibilidade

Segue a regra 8 da seção 2. Campo novo entra como opcional e sobe o MINOR (`1.0` → `1.1`); renomear, remover ou mudar o tipo de um campo sobe o MAJOR. O consumidor aceita qualquer MINOR do MAJOR que conhece. Estes schemas descrevem a versão 1.0 e recusam campos que ela não tem; ao publicar uma 1.1, o arquivo do contrato é atualizado no mesmo commit.

## Divergências da Especificação 1.0

- `GRID_TOO_LARGE` em `ods.s5.heatmap.reply` não está na lista de erros da especificação. Foi proposto ao TRA-1 para a 1.1, enquanto não há onde guardar o arquivo de `heatmap_uri`.
