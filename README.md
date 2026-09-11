# SLA de projetos — Monday → PostgreSQL → BI

**Consumo versão 2.2:** importar apenas `orcamento.gold_projeto_status`. Python entrega uma linha por passagem com datas, duração, retorno, Marca, Talento e responsável de Orçamento. Guia: [OURO_CONSUMO.md](docs/OURO_CONSUMO.md). Validação/publicação: [VALIDACAO_OURO.md](docs/VALIDACAO_OURO.md). Uma Gold de indicadores, uma [quarentena](docs/QUARENTENA_E_IDENTIDADES.md) e regras separadas por módulo. Guia de manutenção: [PRD_ELT_REGRAS.md](docs/PRD_ELT_REGRAS.md). Tempos D+1: execução às 06h, corte à meia-noite; reinício não executa outra carga.

Pipeline `sls_orcamento_pdd`: snapshots de itens, eventos de status, intervalos de permanência e indicadores diários. Python 3.11+, PostgreSQL 16/17, execução headless. Namespace atual na VPS: `dados_globo.orcamento`; dataset futuro: `sla_orcamento_pdd`.

## Executar com o banco da VPS

O `.env` atual aponta para o PostgreSQL existente e seleciona `COMPOSE_FILE=compose.remote.yaml`. As tabelas e a carga histórica já foram transferidas e reconciliadas. O executor existente no EasyPanel usa `loop` às 06h São Paulo; executar os comandos abaixo nesta máquina grava no banco remoto. Confira [o aceite provisório](docs/ACEITE_PROVISORIO.md) e use [o prompt do painel](docs/PROMPT_CLAUDE_EASYPANEL.md) para validar a versão implantada. Para montar o relatório, comece pelo [PRD Power BI](docs/POWER_BI_PRD.md).

```bash
docker compose build pipeline
docker compose run --rm pipeline check-db
docker compose run --rm pipeline validate-gold
docker compose run --rm pipeline validate
docker compose run --rm pipeline health
```

Veja [OPERATIONS.md](OPERATIONS.md) para rede interna, agendamento e backup. Use campos `PG_*`; `DB_*` não é aceito pelo CLI. `check-db` informa também se a conexão usa TLS.

## Instalação local nova com Docker

Esta alternativa usa `COMPOSE_FILE=compose.yaml`, banco `sla_workflow`, schema `sladb` e porta externa `127.0.0.1:55432`. Não use esse modo com o `.env` remoto sem preparar uma configuração local separada.

```bash
# Instalação nova: copie .env.example para .env e preencha token e senha.
docker compose up -d postgres
docker compose --profile job build pipeline
docker compose --profile job run --rm pipeline discover
docker compose --profile job run --rm pipeline backfill
docker compose --profile job run --rm pipeline validate
docker compose --profile job run --rm pipeline daily
```

`daily` sem watermark executa automaticamente o backfill disponível. `replay` recalcula Silver/Gold no último corte bem-sucedido, sem chamar a API e sem alterar o watermark. `health` retorna exit code 1 se a última execução falhou ou está atrasada.

Rotina de desenvolvimento e análise: [VS Code/Python e DBeaver](docs/ROTINA_VSCODE_DBEAVER.md).

## Executar sem container de aplicação

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\sla-pipeline discover
.\.venv\Scripts\sla-pipeline backfill
.\.venv\Scripts\sla-pipeline daily
```

No Linux: `.venv/bin/sla-pipeline`. Execute a partir da raiz, ou use `sla-pipeline --env-file /caminho/.env daily` e configure `RUNTIME_DIR` absoluto. PostgreSQL continua obrigatório. `init-db` cria somente objetos ausentes e atualiza as views; não apaga tabelas.

## Analisar um projeto e entender as tabelas

Abra [as consultas prontas para DBeaver](sql/006_analise_projeto.sql): procure o nome, copie o ID original e consulte a trajetória e o total por etapa. Execute uma consulta por vez. O [guia de relacionamentos](docs/RELACIONAMENTOS_E_KPIS.md) mostra como cruzar tabelas sem duplicar as horas. O [PRD analítico](docs/PRD_ANALITICO.md) explica tabelas, KPIs, estimativas e requisitos para metas de SLA. O [guia de implantação](docs/DEPLOY_PASSO_A_PASSO.md) explica GitHub, VPS e agendamento.

## Regras do cálculo

- **O SLA total começa em Entrada**, no primeiro evento disponível de transição para esse status (`sla_start_utc`). Voltar a Entrada não reinicia o SLA. Se essa entrada não está nos logs, o total fica nulo e o item recebe `inicio_entrada_nao_comprovado`; as permanências por etapa são mantidas. `first_status_at` registra o primeiro trecho disponível, que pode anteceder o início do SLA.
- Eventos de `status_19` ordenados por instante UTC, precisão original e ID. Reentradas geram novos intervalos; eventos sem mudança não reiniciam o relógio.
- `status_to` é o status ocupado pelo intervalo; `status_from` é a etapa anterior. `event_end_id` é o evento que encerrou a permanência.
- Último intervalo termina no instante de corte da execução e mantém `is_open_interval=true`. A duração cresce na próxima execução mesmo sem eventos novos.
- A duração é **tempo corrido**, incluindo finais de semana. Não é contagem de horas úteis nem a fórmula `WORKDAYS` existente no quadro.
- A tabela diária divide cada intervalo à meia-noite de `America/Sao_Paulo`, respeitando inclusive mudanças históricas de horário de verão.
- No resumo, `FINAL_STATUS_LABELS` define encerramento do lead time e exclusão da fila de trabalho. O tempo de permanência em status finais continua nas tabelas de intervalos. Uma reabertura volta a contar o lead time.
- No `.env` local: finais = `Encerrado`, `Declinado pelo Mercado`, `Declinado Internamente`. A decisão é configurável e baseada nos nomes do quadro; não pressupõe que a propriedade `done_colors` esteja preenchida.

## História disponível e qualidade

Backfill pagina todo o histórico **que a API deste board disponibiliza**. Histórico anterior à criação/cópia do board ou fora da retenção do plano não pode ser reconstruído pela API deste quadro. Não se presume que todo item começou em Entrada.

Antes do primeiro evento, o `previous_value` é estendido à criação do item apenas como **inferência**, com `history_quality=initial_inferred`. Sem eventos, o status do snapshot é aplicado desde a criação com `no_history_inferred` e diagnóstico `status_sem_movimento`. Esses trechos são úteis como estimativa, mas não comprovam a permanência histórica. Filtre `history_quality='observed'` para usar apenas intervalos iniciados por eventos reais. Um item terminal sem eventos não tem data de encerramento comprovada: `finalizado_em` e `lead_time_total_min` ficam nulos no resumo; a permanência inferida continua nos intervalos.

Snapshots não reconstituem alterações de Marca, Talento ou pessoas anteriores à primeira coleta. O enriquecimento usa a última versão observada até o início do intervalo; quando não existe, usa a primeira disponível e informa `attribute_source=earliest_available`. Cada intervalo referencia `snapshot_date`. Existe um snapshot por item/board/data local; reexecução no mesmo dia atualiza essa versão.

Itens presentes somente nos logs são preservados, com atributos desconhecidos e fora da fila ativa. Itens que deixam de aparecer no snapshot também saem da fila; isso não prova exclusão ou arquivamento. O tempo do último status observado continua disponível como tal. Divergência entre snapshot e log gera diagnóstico e deixa a idade do status atual nula, sem inventar data de transição.

## Modelo para Power BI

| Objeto | Uso |
|---|---|
| `bronze_monday_activity_log_raw` | Envelope original do log, timestamps, origem do timestamp, chave `event_id` |
| `bronze_monday_item_snapshot_raw` | Snapshot diário, atributos e JSON original de todas as colunas |
| `bronze_monday_board_schema_raw` | Versão do schema do quadro e mapeamento aplicado |
| `silver_monday_status_event_stg` | Eventos tipados e deduplicados |
| `dim_board`, `dim_item`, `dim_status`, `dim_person` | Dimensões com IDs originais, SKs determinísticas e chaves estrangeiras no PostgreSQL |
| `meta_column_mapping` | Catálogo por board/coluna: ID, título, tipo e atributo analítico |
| `bridge_item_person` | Pessoas por papel/coluna e data do snapshot |
| `fct_item_status_interval` | Cada visita a um status, duração, atributos e qualidade |
| `fct_item_status_daily` | Minutos por dia local, item e status |
| `fct_item_sla_summary` | Estado atual, lead time e idade do status atual |
| `gold_project_status` | Tempo acumulado de cada item em cada status |
| `gold_status_metrics` | Média, mediana e p95 **por intervalo**, permanência acumulada e quantidade atual |
| `gold_status_bottlenecks` | Ranking de tempo e fila, excluindo status finais |
| `gold_intervals_local` | Datas locais para apresentação |

No Power BI, conecte em **PostgreSQL**, banco `dados_globo`, schema `orcamento`, por túnel/VPN ou conexão TLS configurada para a VPS e com usuário dedicado de leitura. O endereço do servidor depende desse acesso; o hostname Docker interno não resolve nesta máquina. Relacione `dim_item[item_id]` e `dim_status[status_id]` às tabelas fato. Para pessoas, use a bridge com `snapshot_date`; não some intervalos após um join de múltiplas pessoas sem controlar duplicação. Médias/percentis incluem intervalos abertos e inferidos nas views gerais; aplique filtros de qualidade nas análises que exigem apenas permanências comprovadas.

## Qualidade e contratos

`quality-profile` inspeciona as 20 tabelas sem alterar dados e gera `runtime/quality_<board_id>.json`, com contagens de nulos/vazios e resultado dos contratos. A passagem para análise normaliza textos em cópias, preservando JSON bruto e nulos legítimos. O lote é bloqueado para identidades, tipos e durações inválidas. Campos obrigatórios também recebem NOT NULL no PostgreSQL.

Leia [o padrão de arquitetura e governança](docs/ARQUITETURA_E_GOVERNANCA.md) e [o contrato de campos](docs/CONTRATOS_DE_DADOS.md). Antes de migrar uma base existente: backup, `quality-profile`, `init-db`, `replay`, `validate`. Uma linha incompatível deve ser investigada; não será preenchida automaticamente pela migração.

## Configuração e operação

Todas as opções estão em [.env.example](.env.example). Chaves legadas `TOKEN_MONDAY`, `BOARDS` e `COLUNA` são aceitas; chaves `MONDAY_*` têm precedência. Títulos de status na chave legada são resolvidos para o ID da coluna. `BUSINESS_COLUMNS_OVERRIDE` resolve títulos ambíguos. `STATUS_COLUMN_LABELS_OVERRIDE` mapeia índice → rótulo.

No Windows desta máquina, a biblioteca TLS do Python não completou a conexão com o Monday; `MONDAY_HTTP_TRANSPORT=curl` usa o TLS nativo sem desabilitar certificados. O token é passado por stdin, nunca na linha de comando. No container, `DOCKER_HTTP_TRANSPORT=requests` usa o transporte Python, validado com o quadro real.

- [PRD.md](PRD.md): requisitos acordados e plano de migração futura para BigQuery.
- [docs/RELATIONAL_MODEL.md](docs/RELATIONAL_MODEL.md): chaves, catálogo e joins com novas bases.
- [docs/NEW_STATUSES.md](docs/NEW_STATUSES.md): inclusão de novos status, como Negócio Fechado.
- [OPERATIONS.md](OPERATIONS.md): VPS, cron, backups, monitoramento e recuperação.
- [docs/MAPPING.md](docs/MAPPING.md): IDs e status reais do quadro.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): incremental, idempotência e timestamps.
- [docs/BIGQUERY_DATABRICKS.md](docs/BIGQUERY_DATABRICKS.md): migração e consumo.
- [sql/003_sanity.sql](sql/003_sanity.sql): consultas de conferência.

## Testes

```powershell
.\.venv\Scripts\python -m pytest -q
# PostgreSQL real: use configuração LOCAL de testes, nunca o .env da VPS:
# Os testes criam schemas isolados no banco apontado por PG_*.
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\ruff check src tests
```

Os testes de integração criam schemas `sla_test_*` e não apagam objetos de produção. Em CI, use banco descartável. O teste exige um PostgreSQL configurado no `.env`.
