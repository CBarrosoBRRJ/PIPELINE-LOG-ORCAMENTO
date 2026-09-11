# PRD — SLA de status de projetos no Monday

Versão: 1.2. Atualizado em 11/09/2026. Projeto: `sls_orcamento_pdd`.

Este documento reúne os requisitos originais e as decisões confirmadas durante a implementação. Deve ser lido antes de continuar o projeto, implantar a VPS ou migrar para BigQuery.

## Objetivo

Medir quanto tempo cada elemento/projeto permanece em cada status, identificar filas e gargalos, relacionar os resultados com atributos de negócio e pessoas e permitir o cruzamento com futuras extrações pelo **ID original do item**.

Fonte atual: quadro **Backlog 2026 | Agenciamento**, `board_id=18429499488`, coluna `status_19`. O pipeline é somente leitura na origem. Persistência atual na VPS: PostgreSQL 17, banco `dados_globo`, schema `rede_globo`. A origem local preservada usa PostgreSQL 16, banco `sla_workflow`, schema `sladb`. Destino futuro: BigQuery, dataset `sla_orcamento_pdd`, com consumo também no Databricks.

## Guia de uso analítico e implantação

O objetivo prioritário confirmado é selecionar o projeto X, conhecer sua trajetória e medir quanto tempo permaneceu em cada status, identificando gargalos por etapa. A tabela principal é `fct_item_status_interval`; o cadastro `dim_item` apenas identifica o projeto.

- [PRD analítico](docs/PRD_ANALITICO.md): as 16 tabelas, as quatro views, KPIs, regras de qualidade, retornos e proposta de relatório.
- [Relacionamentos e KPIs](docs/RELACIONAMENTOS_E_KPIS.md): chaves, cardinalidade, joins e modelo inicial para Power BI.
- [Consultas para DBeaver](sql/006_analise_projeto.sql): localizar projeto, trajetória, totais por etapa, diagnósticos, comparação de etapas e fila.
- [Implantação passo a passo](docs/DEPLOY_PASSO_A_PASSO.md): papel do GitHub, transferência para VPS, execução por Docker, rede interna e cron.

O usuário confirmou que não existem metas por etapa: a fase atual é de estudo dos tempos reais para estabelecer padrões. Medir permanência já está implementado. Metas máximas por etapa e a classificação dentro/fora do SLA ainda dependem de definição de negócio e implementação. Não confundir a permanência medida com uma meta já cadastrada. D+1 fechado permanece proposto; o modo atual é corte no início da execução.

## Qualidade e padrão da equipe

O usuário confirmou que organização, tratamento coerente entre camadas e documentação completa são requisitos permanentes para este e os próximos pipelines. Padrão: [ARQUITETURA_E_GOVERNANCA.md](docs/ARQUITETURA_E_GOVERNANCA.md). Contrato de todos os campos: [CONTRATOS_DE_DADOS.md](docs/CONTRATOS_DE_DADOS.md), gerado do metadata e contrato executável 1.0.0.

Implementação: validação de entrada antes da transformação; limpeza textual em cópias, preservando Bronze; validação de tipos, obrigatoriedade, identidade, escopo e duração antes de publicar; NOT NULL em campos obrigatórios PostgreSQL; comando `quality-profile`. Nulos legítimos não são preenchidos artificialmente. Falhas críticas bloqueiam o lote e não avançam o watermark. Não há landing/quarentena durável independente implementada.

Extensão para N projetos deve preservar IDs/SKs e declarar origem, conta, grão, domínio, responsáveis e consumidores. O MVP ainda é um quadro por configuração, com rebuild em memória; não apresentar esse padrão documental como execução distribuída pronta. Metas por etapa, D+1 fechado, alertas externos e executor/cron na VPS continuam pendentes.

## Regras de negócio acordadas

1. O marco inicial do SLA total é sempre **Entrada**. Usar a primeira transição disponível para esse status; reentrada não reinicia o total.
2. Na ausência do evento inicial, registrar `sla_start_quality=unavailable`, diagnóstico `inicio_entrada_nao_comprovado` e SLA total nulo. Não tratar outro status como início nem inventar a data de Entrada.
3. Preservar a permanência de todas as etapas, inclusive retornos, status finais e o último intervalo ainda em aberto.
4. Status novos são descobertos automaticamente pelo ID/índice na mesma coluna. **Negócio Fechado** é uma expansão prevista; a equipe poderá criá-lo no Monday. Ainda não foi criado pelo pipeline.
5. `FINAL_STATUS_LABELS` controla o encerramento do resumo. Configuração local inicial: Encerrado, Declinado pelo Mercado, Declinado Internamente. Incluir Negócio Fechado quando definido como final. A permanência na etapa final continua armazenada.
6. Tempo é corrido, em minutos/horas, incluindo finais de semana. Horas úteis não fazem parte do MVP.
7. UTC na persistência; datas diárias e apresentação em America/Sao_Paulo.
8. Não transformar indisponibilidade de histórico em fato: trechos iniciais/no movimento são explicitamente inferidos, e a data final também fica desconhecida quando não há evento que a comprove.

## Estrutura relacional e identidade

| Chave | Significado | Regra |
|---|---|---|
| `board_id` | ID original do quadro Monday | Identifica origem/configuração |
| `item_id` | **ID original do elemento Monday** | Conservar em todas as novas análises e integrações |
| `event_id` | ID original do log | Deduplicação e rastreabilidade da transição |
| `status_id` | Board + coluna + índice do status | Preservar entre PostgreSQL/BQ/Delta |
| `person_id` | ID original de usuário Monday | Relacionar por bridge com papel e data |
| `interval_id` | Hash determinístico da visita ao status | Reexecução idempotente |
| `item_sk` | UUIDv5 técnico da entidade item | Join analítico estável, sem apagar `item_id` |
| `board_sk`, `person_sk`, `status_sk` | UUIDv5 técnicos das dimensões | Preservados entre PostgreSQL, BQ e Delta |

PostgreSQL deve impor PKs e FKs. As FKs são verificadas ao final da transação (`DEFERRABLE INITIALLY DEFERRED`) para permitir publicação atômica entre camadas. Uma referência inexistente deve abortar o commit inteiro, inclusive o watermark. IDs Monday não são substituídos por sequências locais.

Dimensões: `dim_board`, `dim_item`, `dim_status`, `dim_person`. Relações de pessoas: `bridge_item_person`, cujo grão é item + pessoa + coluna + data do snapshot. Fatos: `fct_item_status_interval`, `fct_item_status_daily`, `fct_item_sla_summary`. Bronze guarda os envelopes originais; Silver guarda eventos tipados.

Ao adicionar outra base, trazer `item_id` e `board_id` e definir o grão antes do join. Não relacionar por nome do projeto, Marca ou posição da linha. Itens copiados no Monday podem ter novos IDs; se for necessário unir cópias, será preciso uma chave de negócio adicional, sem assumir equivalência pelo nome.

## Chaves substitutas e catálogo

### Padrão de chaves substitutas

O MVP acrescenta **chaves substitutas de entidade (`*_sk`)** às dimensões, Silver, bridge e fatos. O algoritmo é UUIDv5, namespace UUID padrão `NAMESPACE_URL`, nome `sls_orcamento_pdd:monday:<entidade>:<ID original>`. A mesma entidade recebe a mesma chave em qualquer ambiente, sem depender de sequência do PostgreSQL ou reenumerar registros no BQ. O algoritmo/namespace é um contrato: **não mudar depois da carga sem migração explícita**.

Nas dimensões, a SK é NOT NULL e UNIQUE. Nesta versão, as PKs de origem/composição já existentes são preservadas para compatibilidade de upsert e migração aditiva. Os relacionamentos técnicos usam FKs compostas `(ID original, SK)` para impedir a associação do ID de um item à SK de outro. Novas análises podem usar `item_sk` internamente e devem conservar `item_id` para interoperabilidade com o Monday. BQ valida a correspondência por ASSERT antes do commit.

`item_sk` depende de item, não de board ou nome: mover/renomear um item não troca sua identidade. Cópias com outro ID são outras entidades. `status_sk` deriva de `status_id`, que inclui board/coluna/índice. Uma fonte adicional deve ter namespace próprio; não mapear automaticamente o mesmo número em sistemas diferentes como a mesma entidade.

Estas são chaves de **entidade**, não de versão histórica. O histórico atual usa snapshots. Uma evolução SCD Tipo 2 deverá criar `item_version_sk` e campos `valid_from`, `valid_to`, `is_current`, mantendo `item_sk`/`item_id` para reconhecer a entidade. Fatos que exigirem o atributo vigente no evento deverão apontar à chave da versão. Não implementar SCD2 apenas renomeando a SK atual.

UUID determinístico favorece portabilidade; ocupa mais espaço que BIGINT. Para volumes muito maiores, medir armazenamento/custo de join antes de adotar uma chave numérica administrada centralmente. Não criar sequências independentes em PostgreSQL e BQ para a mesma dimensão.

### Catálogo de colunas

`meta_column_mapping` registra board, ID da coluna, título, tipo, atributo analítico, se é extraída, se é modelada e se ainda está presente no quadro. A evolução do schema permanece em `bronze_monday_board_schema_raw` por data. A documentação humana está em [docs/MAPPING.md](docs/MAPPING.md).

Todas as colunas retornadas na extração de itens ficam no JSON Bronze. Marca, Talentos Exclusivos, Interveniência e pessoas são materializados para análise; Cliente está ausente no quadro atual e não é deduzido de outro campo. Ao promover uma nova coluna para Silver/Gold, atualizar o mapeamento, aplicar migração aditiva e reprocessar a Bronze quando o dado já existir.

## Operação do MVP

### Proposta de janela D+1 (aguardando definição com o usuário)

Proposta: executar às **03h America/Sao_Paulo**, publicar no BI até **04h** como objetivo operacional, com corte analítico às **00h do mesmo dia** (dia anterior completo). Exemplo: execução em 11/09 publica a referência de 10/09. Intervalos abertos são medidos somente até o corte analítico. A hora de conclusão não é garantia de SLA operacional sem monitoramento e medição na VPS.

**Estado atual:** o código calcula até o instante de início da execução, não aplica automaticamente um corte D+1. A proposta requer separar `extracted_at`, `data_as_of` e `reference_date`, manter watermark de extração independente do corte analítico e adaptar os testes de fronteira.

Não atribuir retrospectivamente à meia-noite os atributos lidos às 03h. O status no corte deve ser reconstruído pelos logs, inclusive transições entre meia-noite e a coleta. Para Marca/pessoas e outros atributos sem logs próprios, guardar o horário real e sinalizar quando a versão do corte é desconhecida. Excluir do universo de referência itens criados depois do corte. Eventos atrasados precisam corrigir a data de referência anterior sem duplicação. No BI, exibir data de referência e horário da última atualização separadamente.

Agendamento final do cron deve ser ajustado ao timezone da VPS; 03h São Paulo equivale a 06h UTC na configuração atual. Até a decisão e implementação específica, não afirmar que as tabelas atuais são um fechamento D+1.

- Um `.env` para configuração e segredos; preservar as chaves legadas. Não imprimir tokens/senhas.
- Backfill completo da história disponibilizada pelo board; janelas menores se necessário para o teto da API.
- Execução diária com sobreposição e página adicional de segurança, upsert por evento e snapshot diário.
- Watermark, Bronze, derivados e métricas publicados atomicamente. Falha não avança o corte.
- Logs estruturados, arquivo de estado, consultas de sanidade, backup e cron documentados.
- Nenhum DROP de produção. Mudanças de modelo são aditivas.

### Estado da VPS em 11/09/2026

O usuário forneceu os dados do PostgreSQL no `.env` e pediu a continuidade. Conexão real confirmada com `dados_globo` (PostgreSQL 17.11); schema `rede_globo` criado com as 16 tabelas, views, PKs, FKs e SKs. A carga local foi transferida em transação, mantendo a origem intacta, e o conteúdo das 16 tabelas foi reconciliado integralmente. Relatório técnico sem credenciais: `runtime/vps_migration.json`.

O executor ainda roda nesta máquina, gravando no banco remoto. **Instalação do executor e cron na VPS dependem do acesso SSH/painel e da rede Docker do banco.** Fazer essa etapa com explicações ao usuário; não afirmar que já existe atualização automática no servidor.

Configuração operacional:

- Campos efetivos: `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`, `PG_SCHEMA`. Campos `DB_*` colados anteriormente não eram consumidos; foram normalizados. Chaves duplicadas e sintaxe inválida agora interrompem o CLI sem exibir valores secretos.
- `.env` atual seleciona `COMPOSE_FILE=compose.remote.yaml`: somente aplicação e cliente de backup opcional, sem provisionar outro PostgreSQL. `compose.yaml` continua disponível para instalações locais novas.
- Acesso desta máquina usa endereço/porta externos. Na VPS, usar hostname/porta internos e configurar `PIPELINE_DOCKER_NETWORK` com `PIPELINE_NETWORK_EXTERNAL=true` para a rede existente. DNS interno só funciona em containers conectados à rede correta.
- `PG_SSLMODE=prefer` negocia TLS quando disponível; a conexão externa testada estava **sem TLS**. Para operação definitiva, usar rede interna Docker; acesso administrativo/BI externo deve usar túnel/VPN ou TLS validado. Configurar `verify-full` e certificados quando houver endpoint TLS; não assumir que `prefer` exige criptografia.
- Manter `PG_DSN` vazio ao usar os campos separados. `check-db` testa conexão em transação somente leitura e informa banco/schema/TLS, sem senha.
- Dados antigos de conexão local foram preservados como `LOCAL_PG_*` para recuperação; não são usados pelo pipeline diário. Backups de `.env` contêm segredos e exigem a mesma proteção do original, fora do Git.
- Conta fornecida é administrativa (`postgres`); criar identidade de execução dedicada e papel de leitura separado para BI durante a configuração conjunta do servidor.
- Backup remoto usa cliente PostgreSQL 17 e inclui somente `PG_SCHEMA`; validar restore em destino vazio/separado e manter cópia fora da VPS.

O corte D+1 acima continua proposto, sem alteração silenciosa da regra analítica durante a migração do banco.

## Migração futura PostgreSQL → BigQuery

### Estratégia

A migração deve preservar a lógica Python e trocar o adapter de armazenamento. O código possui interface `Store`, adapter PostgreSQL, adapter BigQuery e comando `export-bq`. As tabelas/colunas vêm de um metadata comum; IDs naturais e técnicos não mudam.

Isso reduz o trabalho de migração, mas não substitui o provisionamento do GCP e a homologação real. **BigQuery e Databricks ainda não foram provisionados/testados com credenciais reais neste ambiente.**

### Preparação

1. Ler este PRD, [docs/BIGQUERY_DATABRICKS.md](docs/BIGQUERY_DATABRICKS.md) e [OPERATIONS.md](OPERATIONS.md).
2. Confirmar projeto GCP, faturamento, região, dataset, identidade de execução, permissões e orçamento.
3. Preencher no mesmo `.env`: `BQ_PROJECT`, `BQ_DATASET`, `BQ_LOCATION` e, se necessário, `BQ_KEYFILE`. Preferir identidade de execução/ADC quando disponível; não guardar keyfile no código.
4. Instalar o extra: `python -m pip install -e '.[bigquery]'`. O Docker padrão atual é PostgreSQL; preparar uma imagem com esse extra para trocar o destino.
5. Criar um dataset novo de homologação; conferir tipos, partições, clustering e views.

### Transferência dos dados

1. Fazer backup do PostgreSQL e registrar o último watermark bem-sucedido.
2. Executar `sla-pipeline export-bq`: copiar Bronze, snapshots, dimensões, catálogo, bridge, fatos e estado.
3. Usar cargas em staging com TTL e MERGE por chaves; publicar o payload e watermark em uma transação BQ. Não usar append cego.
4. Preservar `item_id`, `board_id`, `event_id`, `status_id`, `interval_id`, datas UTC, flags de qualidade e versões de atributos.
5. Manter um único scheduler/worker por board. O lock do adapter BQ atual é local ao host; adicionar lease distribuído antes de usar vários workers.

### Homologação obrigatória

- Contagem por tabela/board e quantidade de chaves distintas iguais à origem.
- Zero duplicatas nas chaves naturais e zero referências órfãs nas relações declaradas.
- Soma de minutos por item/status e por dia reconciliada, com tolerância numérica explícita.
- Mesmo status atual, mesma fila, mesma mediana/p95 no mesmo corte.
- Mesma regra de início em Entrada e mesmos casos de início/fim não comprovados.
- Executar novamente no mesmo corte sem duplicar dados.
- Simular falha antes do commit e confirmar que o watermark não avançou.
- Testar eventos atrasados, novos status, reentrada e intervalos abertos.
- Conferir custo, duração do job e consumo do Power BI/Databricks.

BigQuery aceita declarações de PK/FK, mas **não impõe essas constraints**. O pipeline deve verificar unicidade e relacionamentos antes da publicação; não confiar em uma FK declarada para bloquear um registro inválido. [Documentação oficial](https://docs.cloud.google.com/bigquery/docs/primary-foreign-keys).

### Corte para produção e retorno

1. Pausar o cron PostgreSQL e anotar o corte final. Fazer a sincronização final e comparar novamente.
2. Alterar `TARGET_DB=bigquery`; iniciar somente o novo scheduler.
3. Rodar `daily`, validar e apontar o consumidor para as tabelas/views BQ.
4. Manter PostgreSQL e backup durante a estabilização; não remover o banco antigo na migração.
5. Em caso de erro, pausar BQ, voltar para PostgreSQL e recuperar os eventos posteriores ao watermark antigo. Se a janela de retenção da origem não cobrir a recuperação, transportar a Bronze BQ antes de retomar. A sincronização reversa não está automatizada no MVP.

Particionamento: data do evento, data do snapshot, início do intervalo ou `dt`, conforme a tabela. Clustering: board, item e status quando aplicável. O BQ não é substituto transacional para aplicações operacionais; aqui será o destino analítico.

## Evolução e escala

MVP: um board por configuração e eventos incrementais, com rebuild dos derivados do board em memória. Para crescer, medir tamanho de Bronze, número de intervalos, memória e duração antes de ampliar a carga. Próxima evolução: recalcular somente itens/partições afetados, incluindo todos os intervalos abertos; persistir lotes de extração; distribuir por board com coordenação; definir retenção de snapshots e observabilidade central.

Novas tabelas analíticas devem compartilhar `item_id`/`board_id`, preservar o grão e usar migrações aditivas. Não aumentar indiscriminadamente uma tabela única nem duplicar atributos sem origem/versionamento.

## Critérios de entrega e retomada

### Mapa de manutenção e boas práticas

| Mudança/operação | Onde alterar | Verificação obrigatória |
|---|---|---|
| Novo status na mesma coluna | Descoberta automática; `.env` apenas se for final | `discover`, `daily`, teste de nova transição |
| Renomear final | `FINAL_STATUS_LABELS` e documentação | `replay` e conferência dos encerramentos |
| Trocar board/coluna | `.env`, revisar `docs/MAPPING.md` | Backfill do novo escopo e conferência de IDs/retenção |
| Materializar atributo | Extract, metadata, transform | Migração aditiva, catálogo, teste de valor/versão e `replay` se Bronze já contém o campo |
| Nova tabela | Metadata comum, transform e stores | Declarar grão, PK, FKs, upsert e equivalência BQ |
| Alterar geração de SK | `models/keys.py` | Plano explícito para migrar todas as referências; nunca alterar silenciosamente |
| Nova origem | Novo client/namespace de identidade | Preservar ID da fonte e definir correspondência entre entidades |
| Corrigir cálculo | Transformações puras e teste do problema | `replay`, reconciliação e regressão dos indicadores |
| Atualizar schema | Metadata e migração aditiva | Executar `init-db` duas vezes, testar com base preenchida, regenerar DDL com `scripts/generate_ddl.py` |
| Atualizar dependências/API | `pyproject.toml` e versão no `.env` | Testes, descoberta e lote de integração antes de produção |
| Falha/reexecução | `OPERATIONS.md` e arquivo de estado | Watermark preservado; sem duplicatas/commits parciais |
| Credenciais | `.env`/identidade de execução | Sem segredos em logs; papel de leitura separado para BI |
| Backup/restore | `scripts/backup.sh` | Restore em banco vazio/separado; cópia fora da VPS |
| Migração BQ | Seção de migração deste PRD | Homologação real, ASSERTs, corte único e retorno |
| Escala | Itens afetados, partições e coordenação | Medir custo/memória/duração e testar atrasados/intervalos abertos |

**Padrões permanentes:** UTC na persistência; nomes e grãos explícitos; original em Bronze; transformações independentes do banco; PK/FK e SK consistentes; transação antes de avançar watermark; erro com saída não zero; retentativas limitadas; logs sem segredos; diagnóstico de desconhecido sem inventar valores; testes de casos reais; documentação atualizada junto da mudança.

**Implementado:** snapshots, descoberta de schema/status, catálogo, chaves naturais e SKs determinísticas, constraints PostgreSQL, testes, armazenamento local e PostgreSQL remoto com dados reconciliados, backfill/daily/replay, adapter/DDL/validações BQ e documentação. **Ainda não implantado:** executor/cron na VPS, BigQuery real, Databricks real, SCD2 de atributos, processamento distribuído, rebuild seletivo e alertas externos. Não apresentar essas evoluções como prontas em produção.

**Decisões desta sessão:** manter `item_id`; início sempre em Entrada; Negócio Fechado previsto e dinâmico; distinguir evidência de inferência; PostgreSQL primeiro; SK aditiva sem quebrar chaves; mesma identidade no BQ; PostgreSQL da VPS configurado após o fornecimento do `.env`; acesso ao servidor pendente para instalar o executor e agendar.

O MVP deve passar testes unitários e integração PostgreSQL, backfill real, execução incremental real, sanidade de durações, idempotência e integridade referencial. A implantação remota e a migração BQ são etapas separadas, realizadas com o usuário.

**Pedido sugerido para retomada futura:**

> Leia PRD.md, README.md e docs/BIGQUERY_DATABRICKS.md deste projeto. Vamos migrar o pipeline de SLA do PostgreSQL para BigQuery seguindo os critérios de homologação e retorno do PRD. Preserve todos os IDs, a regra de início em Entrada, o histórico Bronze e o watermark. Primeiro verifique o estado atual e as credenciais disponíveis; não remova o PostgreSQL.
