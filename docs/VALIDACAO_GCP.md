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

Revisar plan autenticado e provisionar APIs/IAM/bucket/segredo; inicializar uma base nova via init-db/backfill (decisão atual: não importar PostgreSQL/checkpoint anteriores); executar load real incluindo caso vazio em ambiente isolado; comparar IDs, quantidades e horas; testar recuperação em ambiente isolado; validar consumo Power BI; ligar Scheduler e observar a primeira execução diária. Não criar dados fictícios no dataset de produção.

## Revalidação do roteiro de instalação nova — 16/09/2026

- Revisados os **93 arquivos versionados existentes**: código, testes, configuração, infraestrutura, workflows, contratos gerados, SQL, DAX e documentação. Acrescentado `tests/test_deployment.py`. DAX/consultas foram inspecionados, não executados no Power BI/BigQuery reais. Dependências instaladas e arquivos privados não foram tratados como código a limpar.
- Rodada final com `RUN_MIGRATION_TESTS=1 .venv/Scripts/python.exe -m pytest -q`: **127 passaram, nenhum ignorado**, em 31,00 s. PostgreSQL 16 de teste isolado em loopback 55439; container temporário removido ao terminar. Banco existente na porta 55432, VPS e runtime reais não foram alterados. Sem a opção de integração: 124 passaram, 3 ignorados.
- Ruff e `pip check`: aprovados. O Python global não possui pytest/ruff; a validação usou o ambiente virtual do projeto.
- `docker build -t sla-orcamento:gcp-reviewed .`: aprovado. Calendário 2026 executado, UID 10001 e ausência de `/app/.env` verificados; `pip check` no container aprovado.
- Terraform fmt e validate aprovados com 1.9.8/provider 6.50.0. O init tentou acessar registry.terraform.io e teve timeout; validate foi repetido com TF_DATA_DIR apontando ao cache privado já existente. Não houve plan/apply autenticados. Sintaxe dos scripts Bash aprovada em container; o mount do Google Drive não era acessível ao Docker, então a verificação usou os scripts por stdin, sem executá-los.
- Links Markdown locais, `git diff --check` e regeneração de contratos/DDL conferidos; nenhum desvio dos arquivos gerados.
- Corrigidas exclusões de `.tfplan`/`.tfvars.json` dos contextos de build e `.tfvars.json` do Git, removidos dois ramos CLI legados inacessíveis e ocultado valor rejeitado na conversão ISO8601. Testes novos cobrem esses arquivos de deploy, erro de timestamp e bloqueio de daily antes de backfill.
- Guias, prompts e README atualizados para destino vazio, primeira coleta `init-db`/`backfill`, validação manual e agenda confirmada às 06h. Nenhuma regra de cálculo, contrato ou lógica de publicação alterada.
- `.env` local conferido apenas por indicadores, sem imprimir valores: permanece legado, sem bucket configurado e sem corresponder à configuração BQ confirmada. Foi preservado. Deploy usa gcp.env.yaml e Secret Manager; execução local opcional requer `.env.gcp` preparado separadamente.
- Referência de execução com substituições de argumentos conferida na documentação oficial do Cloud Run. Nenhum comando de implantação/coleta foi executado contra o GCP ou Monday nesta revisão.

Nenhum recurso GCP, segredo, tabela real ou agendamento foi criado/alterado nesta sessão. A publicação no GitHub não equivale ao deploy no GCP. `.env`, PostgreSQL e checkpoint existentes foram preservados.

## Limpeza realizada

48 arquivos obsoletos removidos: Compose, cron/backup VPS, exemplos Databricks, SQL PostgreSQL antigo, escritores PostgreSQL, SQLite gravável, wrappers de execução, transporte curl e documentação/testes dessas funcionalidades retiradas. Conteúdo versionado anterior pode ser recuperado no commit fd8226e; arquivos de dados, backups e volumes não foram removidos.

O código diário usa somente BigQuery/GCS. migration/readers.py preserva uma ponte mínima de leitura do histórico anterior, com driver opcional. Schemas e projeções ficaram livres de dependências SQLAlchemy. Governança, mapeamento, regras e operação foram reescritos para o fluxo atual. Os guias de aprendizado e prompts explicam a implantação sem assumir recursos já criados.
