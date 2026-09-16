# Processamento Python e estado privado

O fluxo atual é ETL: extrai Monday, transforma em Python e carrega somente a saída pronta no BigQuery.

1. Descoberta: `services/extract.py` identifica colunas, rótulos e mapeamentos explícitos.
2. Captura: schema do quadro, snapshots cadastrais e eventos são preservados em Bronze.
3. Reconstrução: `services/transform.py` deduplica eventos, ordena transições e calcula passagens, resumos e coleções diárias internas.
4. Governança: `rules/` aplica identidade, elegibilidade, pessoas, corte D+1 e calendário.
5. Gold: `services/gold.py` une cadastros e evidências, aplica exclusões por projeto e mantém IDs.
6. Consumo: `models/consumption.py` oculta estimativas no consumo; `models/bq_consumption.py` acrescenta horas úteis.
7. Persistência: `db/bq.py` salva estado no GCS e publica sla_orcamento atomicamente. `db/gcs.py` gerencia objetos e trava por geração.

## Por que manter coleções internas?

Bronze permite replay sem depender de a API ainda ter eventos antigos. Dimensões, fatos, catálogos, problemas de qualidade e execuções mantêm identidade e auditabilidade. São objetos dentro do checkpoint JSON gzip, não tabelas para o usuário administrar. Removê-los mudaria o contrato histórico e prejudicaria a migração.

Inventário: [contratos internos](CONTRATOS_DE_DADOS.md). Campos públicos: [sla_orcamento](CONTRATO_SLA_ORCAMENTO.md). Decisões: [governança](ARQUITETURA_E_GOVERNANCA.md).

## Organização do código

- `clients/`: acesso Monday via requests, com retries e tratamento de falhas.
- `models/`: contratos, chaves e projeções.
- `rules/`: regras de negócio.
- `services/`: extração, transformação, qualidade, revisão e saúde.
- `pipelines/runner.py`: coordenação de backfill, daily e replay.
- `db/`: exclusivamente BigQuery/GCS e serialização.
- `migration/`: leitura opcional do checkpoint e PostgreSQL antigos; sem DDL/DML.
- `deploy/`, `infra/`, `.github/workflows/`: execução, infraestrutura e entrega.

PostgreSQL, cron/VPS, Databricks e Compose não são destinos ativos. A versão histórica continua recuperável no Git; o corte anterior à migração GCP é `fd8226e`.
