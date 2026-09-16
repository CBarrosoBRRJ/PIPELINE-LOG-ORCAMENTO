# Evidências locais — migração GCP v4

Verificado em 16/09/2026. Estas evidências não constituem implantação ou homologação no projeto corporativo.

## Executado

- `RUN_MIGRATION_TESTS=1 python -m pytest -q`: **120 passaram, nenhum ignorado**. Inclui três integrações do importador somente leitura em PostgreSQL 16 local isolado, porta 55439; nenhum teste foi enviado à VPS. Sem a opção de integração, esses três casos são ignorados. A contagem substitui a suíte anterior: testes de escritores/cron removidos deram lugar a testes do fluxo GCP e importador.
- `python -m ruff check src tests scripts/generate_ddl.py scripts/generate_contract_docs.py`: aprovado.
- Geradores de DDL e contratos executados. BigQuery DDL contém uma única tabela com 39 campos; coleções privadas não geram tabelas BQ.
- `docker build -t sla-orcamento:gcp-clean .`: aprovado, Python 3.11 Linux, instalação das dependências e usuário não root UID 10001; ausência de SQLAlchemy/psycopg no runtime confirmada. CLI sem loop ou comandos de escrita/migração PostgreSQL.
- Calendário 2026 executado no container: 10 datas BR PUBLIC, incluindo Sexta-feira Santa e Consciência Negra. Sem feriados extras.
- `bash -n` nos dois scripts de deploy/agendamento: aprovado; nenhum script foi executado contra GCP.
- Terraform 1.9.8: fmt, init sem backend e validate aprovados via executável Windows; provider Google 6.50.0 validado e checksums Windows/Linux guardados em infra/.terraform.lock.hcl. O problema anterior de DNS no container foi contornado sem alterar a rede. Nenhum plan autenticado/apply executado.
- Links Markdown locais conferidos; git diff --check sem erros. Geradores executados e contrato preservado.

## Comportamentos cobertos

Os testes GCP usam doubles compatíveis com as interfaces dos SDKs, não os serviços reais:

- Carga inicial, incremento sem duplicar eventos, estado durável apesar de runtime efêmero, uma tabela apenas.
- Segunda execução diária ignorada; falha de extração preserva watermark e reserva.
- Dois escritores, conflito de geração e remoção somente da geração exata da trava.
- Perda da resposta da submissão BQ; recuperação com o mesmo job ID.
- Interrupção depois da carga e antes da promoção GCS; retomada sem outra carga.
- Job ainda rodando bloqueia nova publicação; erro terminal preserva a carga anterior.
- Exclusão de todos os projetos produz Gold vazia; reinclusão preserva IDs e Bronze.
- Checkpoint ausente, tabela existente sem recibo, referência órfã e alteração externa bloqueiam publicação.
- Migração reconcilia fingerprint interno; reserva administrativa mantém referências aos artefatos publicados.
- Linha do tempo segunda/terça com retorno e término: horas úteis por passagem `NULL, 2, 3, 5, 6`; total desde Entrada comprovada até término = 8h.
- Almoço, fins de semana, feriados, múltiplos anos, intervalos negativos, timestamps sem fuso e início desconhecido.

## Pendente de homologação

Revisar plan autenticado e provisionar APIs/IAM/bucket/segredo; migrar o par checkpoint/PostgreSQL real; executar load real incluindo caso vazio em ambiente isolado; comparar IDs, quantidades e horas; testar recuperação em ambiente isolado; validar consumo Power BI; ligar Scheduler e observar a primeira execução diária. Não criar dados fictícios no dataset de produção.

Nenhum recurso GCP, segredo, tabela real ou agendamento foi criado/alterado nesta sessão. A publicação no GitHub não equivale ao deploy no GCP. `.env`, PostgreSQL e checkpoint existentes foram preservados.

## Limpeza realizada

48 arquivos obsoletos removidos: Compose, cron/backup VPS, exemplos Databricks, SQL PostgreSQL antigo, escritores PostgreSQL, SQLite gravável, wrappers de execução, transporte curl e documentação/testes dessas funcionalidades retiradas. Conteúdo versionado anterior pode ser recuperado no commit fd8226e; arquivos de dados, backups e volumes não foram removidos.

O código diário usa somente BigQuery/GCS. migration/readers.py preserva uma ponte mínima de leitura do histórico anterior, com driver opcional. Schemas e projeções ficaram livres de dependências SQLAlchemy. Governança, mapeamento, regras e operação foram reescritos para o fluxo atual. Os guias de aprendizado e prompts explicam a implantação sem assumir recursos já criados.
