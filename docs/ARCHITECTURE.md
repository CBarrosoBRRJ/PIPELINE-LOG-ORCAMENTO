# Arquitetura e contrato de dados

Modelo atual 2.2: consulte [PRD_ELT_REGRAS.md](PRD_ELT_REGRAS.md). Abaixo fica a descrição técnica da reconstrução; consumo agora usa uma Gold e uma quarentena, sem as views antigas. Corte de extração e corte D+1 da Gold são distintos.

```text
Monday GraphQL (somente leitura)
  ├─ schema/colunas → mapeamento dinâmico
  ├─ items_page + next_items_page → snapshots diários
  └─ activity_logs → paginação + deduplicação
          ↓
Bronze: envelopes originais + observação do schema
          ↓ transformação Python pura
Silver: eventos tipados, dimensões, bridge com snapshot_date
          ↓
Gold de consumo: gold_projeto_status / saneamento: quarentena_projeto
          ↓
PostgreSQL → Power BI / migração BigQuery → Databricks
```

## Execução incremental

O corte é capturado antes da leitura. Os logs têm `to=corte`, evitando deslocamento das páginas por novos eventos. A janela diária começa no menor valor entre watermark e `corte-RUN_WINDOW_HOURS`, menos `OVERLAP_MINUTES`. Uma página adicional é lida depois da fronteira. A condição usa `created_at` nativo, porque é a ordenação da API; o timestamp de negócio usa `changed_at` quando válido.

Backfill usa janelas de `ACTIVITY_WINDOW_DAYS` entre a criação do board (ou `BACKFILL_FROM`, se posterior) e o corte. Cada janela pagina até o fim. Ao atingir o teto documentado de 10.000 logs, subdivide o período e deduplica a fronteira por `event_id`. Uma janela saturada de até um segundo causa erro explícito; não é publicada como carga completa.

Bronze usa upsert por `event_id`, preservando `ingested_at` original. Snapshot usa `(board_id,item_id,snapshot_date)`. Recalcular todos os derivados do board garante correção de eventos fora de ordem, retornos a etapas anteriores e crescimento de intervalos abertos. Não há cursor de item persistido entre dias: o snapshot completo é necessário para atributos e fila atual; `last_item_page_cursor` permanece nulo após sucesso.

O store recebe um único payload. Em PostgreSQL, Bronze, Silver, Gold, métricas e watermark são gravados numa única transação. Derivados são substituídos somente para o `board_id` processado, mantendo histórico de snapshots e eventos. Advisory lock por board impede duas cargas concorrentes. Falha de extração, validação ou carga não avança o watermark. A camada de configuração não imprime tokens, DSNs ou exceções de driver que possam incluir parâmetros.

## Timestamps

Precedência: `data.value.changed_at` → `data.changed_at` → `activity_logs.created_at`. Valores inválidos de `changed_at` tentam o próximo fallback. Se nenhum timestamp seguro estiver disponível, a carga falha em vez de inventar a data de ingestão.

O `created_at` nativo do Monday usa **Unix em unidades de 100 ns (17 dígitos)**. Divide-se por 10.000.000 para segundos. A implementação usa Decimal, preserva o original e trunca somente a fração inferior a microssegundo, precisão suportada por PostgreSQL. Também aceita Unix s/ms/us/ns com comprimentos explícitos. ISO sem timezone ou Unix ambíguo é rejeitado. O original resolve empates dentro do mesmo microssegundo.

Todos os campos temporais persistidos são UTC/TIMESTAMPTZ. `snapshot_date` e `dt` são datas locais. O instante de corte atribuído ao snapshot representa a execução, não uma garantia de que o Monday congelou o board durante a paginação. Mudanças concorrentes são diagnosticadas quando detectáveis.

## Escopo e escala

MVP para um board por configuração, parametrizável. `item_id` Monday é global; status técnico inclui board e coluna. Todas as tabelas grandes têm índices ou particionamento apropriados ao destino. Neste MVP, eventos/snapshots e fatos derivados são processados em memória; para muitos boards ou milhões de intervalos, substitua o rebuild integral por partições de itens afetados preservando o mesmo contrato e testes.

As dimensões de status usam índice estável e rótulo atual. Os textos históricos originais estão na Bronze/Silver. Pessoas são preservadas por coluna e data; IDs de equipes continuam em JSON, sem fingir que uma equipe é uma pessoa. A resolução de nomes usa `users`; sem permissão, mantém ID com diagnóstico no relatório.

## Referências verificadas

- [Monday — activity logs](https://developer.monday.com/api-reference/reference/activity-logs): ordem reversa, paginação e unidade de timestamp.
- [Monday — items page](https://developer.monday.com/api-reference/reference/items-page): cursores e itens ativos.
- [Monday — rate limits](https://developer.monday.com/api-reference/docs/rate-limits): retentativas e orçamento de chamadas.
- [BigQuery — transactions](https://docs.cloud.google.com/bigquery/docs/transactions): publicação atômica do payload e watermark.

## Integridade relacional e catálogo

`dim_board` identifica o quadro; `item_id` mantém o ID original do elemento. PKs e FKs PostgreSQL impedem duplicatas e órfãos, com verificação diferida até o commit. `meta_column_mapping` cataloga todas as colunas extraídas e indica quais foram materializadas para análise. O histórico completo do schema fica em Bronze. Alterações de tabelas/constraints existentes são aditivas; `init-db` aplica a migração automaticamente.
