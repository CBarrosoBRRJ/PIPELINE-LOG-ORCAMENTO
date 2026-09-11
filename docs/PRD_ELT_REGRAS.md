# PRD da ELT — manutenção 3.0

**Arquitetura atual:** código Python → checkpoint privado no volume → uma tabela PostgreSQL pronta. Regras/contrato 2.2.0 preservados; a migração de armazenamento não altera os cálculos. Comece pelo [PRD principal](../PRD.md) e siga o [procedimento de operação](../OPERATIONS.md).


Versão 2.2.0 · 11/09/2026. Este é o mapa atual para implementar, revisar e operar regras. O [guia de consumo](OURO_CONSUMO.md) explica os campos e o Power BI; o [contrato gerado](CONTRATOS_DE_DADOS.md) registra tipos, chaves e nulabilidade. Documentos marcados como legados não definem o modelo novo.

## 1. Resultado e limite do produto

O Python extrai, trata, valida e publica `dados_globo.orcamento.gold_projeto_status`. O Power BI importa somente essa tabela. Uma linha significa **uma passagem de um projeto por um status**, com data/hora de entrada e saída, duração, Marca, Talento e responsável da coluna Orçamento. Retornar a uma etapa gera outra passagem legítima, com `eh_retorno=true`; não é duplicidade.

O produto mede permanência corrida, inclusive noites e finais de semana. Não existem metas de SLA definidas. A primeira etapa de negócio é Entrada, mas a primeira linha histórica disponível pode ser outra: não inventamos eventos ou datas ausentes. A comparação de desempenho usa `elegivel_comparacao=true` (passagens observadas, encerradas e sem divergência detectada). Os demais tempos são apresentados com sua qualidade explícita.

## 2. Horário, corte e recuperação

Configuração: `CRON_SCHEDULE=0 6 * * *`, `PREFERRED_TIMEZONE=America/Sao_Paulo`, uma réplica, comando `loop`. O processo espera o próximo horário; subir ou reiniciar o container **não dispara carga imediata**. Não instalar outro cron junto com esse loop.

Exemplo: execução de 12/09 às 06h → Gold com `corte_local=12/09 00:00`, cobrindo tempos até o fim de 11/09. Entradas de status exatamente à meia-noite pertencem ao próximo fechamento. A última passagem incluída tem saída nula e duração limitada ao corte. Projetos que só começaram depois desse limite não aparecem nessa publicação.

Há dois relógios diferentes:

| Relógio | Uso |
|---|---|
| `etl_watermark.last_run_utc` | Início da coleta bem-sucedida; referência da extração incremental |
| `gold_projeto_status.corte_utc/local` | Limite exclusivo do dia fechado para tempos e sequência |
| `cadastro_referencia_utc` | Quando o cadastro de Marca, Talento, responsáveis e atividade foi observado |

A API fornece o cadastro observado durante a coleta. **Não afirmamos que esses atributos estavam assim à meia-noite ou na passagem antiga.** Marca, Talento, responsável e `projeto_ativo` são a atribuição cadastral disponível, com data de referência. O status publicado é a última etapa do histórico anterior ao corte; divergências da origem continuam sinalizadas. Uma correção de cadastro pode reclassificar todo o histórico.

Antes da extração agendada, o executor grava uma reserva na coleção privada `etl_run`: `run_id` UUID determinístico de pipeline + data local, `mode=scheduled`. A checagem de chave sob advisory lock e a persistência no checkpoint impedem uma segunda reserva da mesma data. Reinício, outro processo ou repetição do comando `daily` não duplicam uma data já reservada. O registro passa a `success` na publicação ou `failed` em falha; uma queda abrupta pode deixá-lo `running`, o que também bloqueia repetição automática.

É uma tentativa automática por dia, sem retry de lote. Retries de requisições HTTP dentro da mesma tentativa não são cargas adicionais. Se a VPS estiver desligada às 06h, não há como garantir execução naquele instante: o loop espera o próximo horário quando voltar. Corrigir a causa e executar recuperação manual quando necessário. `daily` manual também usa a reserva diária; `backfill` é recuperação excepcional autorizada e pode consultar o histórico completo. `replay` recalcula a partir do material já coletado, sem Monday e sem avançar o watermark. Nenhum desses comandos deve ser colocado como segunda tarefa automática.

O primeiro ambiente novo precisa de `backfill` antes de ativar o agendador. A regra de reserva durável está homologada para PostgreSQL. O agendador equivalente em BigQuery é uma etapa futura da migração corporativa.

## 3. Passo a passo da transformação

1. **Configuração:** `config.py` lê variáveis sem expor segredos. Confere quadro, coluna de status, títulos/overrides, fuso e finais. `pipelines/runner.py` controla a execução e o lock.
2. **Descoberta:** `services/extract.py::discover` lê IDs, títulos e tipos das colunas; identifica status e pessoas. Mapeamento ambíguo bloqueia publicação. Status novos da mesma coluna são descobertos pelo índice; novos finais exigem atualização explícita de `FINAL_STATUS_LABELS`.
3. **Coleta:** pagina todos os itens ativos e reconcilia a contagem do quadro. Consulta os logs por janelas limitadas, com sobreposição incremental e página de segurança. Eventos são identificados pelo ID original. Repetição de página ou janela saturada não resolvida provoca falha.
4. **Bronze:** mantém envelopes originais de logs, snapshots dos itens e schema do quadro. `merge_rows` deduplica por PK. Snapshot é uma observação por item/data, não cada alteração do cadastro. O histórico de eventos não deve ser reconstruído apenas a partir do estado atual do Monday.
5. **Tratamento:** `services/clean.py` valida entradas e limpa cópias: Unicode NFC, espaços e vazios. Não muda IDs nem JSON bruto; não preenche desconhecidos com zero.
6. **Prata e tempos técnicos:** `services/transform.py` ordena os eventos, mantém empates na ordem nativa, deduplica movimentos sem mudança de status e constrói intervalos contíguos. Separa observado de inferido, calcula resumo e distribuição diária e reconcilia as durações.
7. **Elegibilidade/identidades/pessoas:** módulos em `rules/` aplicam as regras abaixo ao cadastro disponível. A exclusão remove o projeto inteiro da Gold. Diagnósticos registram motivo e versão; não descartam a evidência usada para a decisão.
8. **Gold D+1:** `services/gold.py` enriquece as passagens; `rules/cutoff.py` retém somente entradas anteriores ao corte, limita a última duração e recalcula status no corte, primeira/última linha e totais comprovados. Não altera a Bronze ou os intervalos técnicos da coleta.
9. **Validação:** contrato + referências internas + reconciliação com origem + sequência + retornos + conjunto exato de passagens elegíveis. PK, NOT NULL, UNIQUE, índice parcial e CHECKs da Gold complementam as regras Python; não existem FKs para tabelas removidas.
10. **Publicação:** `db/consumer.py::commit` prepara estado durável no volume, substitui Gold e recibo em uma transação PostgreSQL, depois promove o checkpoint. Falha recupera a geração apontada pelo recibo. A reserva operacional é publicada antes da extração para sobreviver à falha e impedir repetição automática. Não existe transação distribuída nativa entre SQLite e PostgreSQL.

O parsing/tratamento ocorre em memória antes da preparação do checkpoint candidato. Não há landing independente anterior à transformação. O termo ELT descreve o fluxo de dados; operacionalmente há ETL em Python e replay das evidências guardadas no volume. Não há tratamento pesado dentro do Power BI.

## 4. Onde ficam as regras

| Arquivo | Responsabilidade | Testes principais |
|---|---|---|
| `services/clean.py` | Limpeza sem modificar a fonte | `tests/test_contracts.py` e testes de transformação |
| `services/extract.py` | Colunas, paginação, parsing, IDs de status | Testes de extração/cliente |
| `services/transform.py` | Cronologia, Entrada, permanência, inferências | `tests/test_transform.py` |
| `rules/eligibility.py` | Exclusão integral de projetos e códigos dos motivos | `tests/test_gold.py` |
| `rules/identities.py` | Catálogo, normalização e aprovação canônica | `tests/test_gold.py`, `tests/test_postgres.py` |
| `rules/people.py` | Orçamento e demais papéis, deduplicação de pessoas | `tests/test_gold.py` |
| `rules/cutoff.py` | Fechamento diário e projeção dos tempos até o limite | `tests/test_cutoff.py` |
| `rules/__init__.py` | Versão semântica das regras | Versão gravada na publicação |
| `services/gold.py` | Montagem e reconciliação da tabela final | `tests/test_gold.py`, `tests/test_cutoff.py` |
| `services/scheduler.py` | Horário diário sem carga ao iniciar | `tests/test_scheduler.py` |
| `db/consumer.py`, `db/checkpoint.py` | Reserva diária, estado durável, recuperação e publicação de tabela única | `tests/test_consumer.py` |
| `db/postgres.py` | Adaptador legado de migração e lock PostgreSQL; não usado para criar tabelas na rotina atual | `tests/test_postgres.py` |
| `models/schemas.py`, `models/contracts.py` | Grão, tipos, relações e validações portáteis | Testes de contrato, chaves e PostgreSQL |

### Exclusões vigentes

| Código | Condição | Efeito |
|---|---|---|
| `talento_ambas_colunas` | Talento e Interveniência preenchidos, mesmo texto | Excluir projeto de toda Gold |
| `talento_multiplo` | Vários IDs no dropdown ou lista textual explícita | Excluir projeto de toda Gold |
| `talento_squad` | Squad de Talentos | Excluir projeto de toda Gold |
| `talento_nao_individual` | Coletivo/organização identificado ou aprovado como tal | Excluir projeto de toda Gold |
| `talento_identidade_pendente` | Interveniência sem pessoa individual revisada | Quarentena; excluir projeto da Gold |
| `talento_revisao_manual`, `marca_revisao_manual` | Grafia/identidade marcada como `quarantined` no catálogo | Quarentena; excluir projeto da Gold |

Os motivos podem se sobrepor. A regra textual identifica vírgula, ponto e vírgula, quebra de linha, `+` e `&`/`/` entre espaços. Uma pessoa individual aprovada pode esclarecer pontuação do nome; não anula múltiplos IDs nem ambas as colunas preenchidas. A lista de coletivos conhecidos é explícita, não um classificador infalível de qualquer nome.

Marca/Talento nulo não exclui automaticamente o projeto. Interveniência ainda não revisada exclui o projeto inteiro da Gold e gera `talento_identidade_pendente` na quarentena. Uma grafia de Marca/Talento explicitamente marcada como `quarantined` também bloqueia o projeto. Os exclusivos com nome único são classificados como `cadastro_exclusivo`; isso não significa revisão humana de toda grafia. Rankear pessoas exige verificar cobertura e excluir nomes vazios.

### Identidades e erro de digitação

O mecanismo automático limpa formato; o catálogo `meta_entity_mapping` resolve equivalência real. Duas grafias da mesma pessoa ou Marca recebem o mesmo `canonical_id`, nome e tipo, somente após revisão. Não unir pessoas por similaridade, nem converter coletivos em pessoas individuais. Não há IA externa ou serviço pago neste processo.

Alterar aliases no DBeaver: localizar os candidatos, revisar com a equipe, preencher identidade/tipo/revisor, aprovar e atualizar `updated_at`. Não alterar `source_key` para corrigir o nome. A próxima carga aplica a revisão; `replay` antecipa a aplicação usando a coleta já existente. Aprovações conflitantes ou incompletas bloqueiam a publicação; o pipeline nunca sobrescreve revisão humana.

## 5. Como acrescentar ou mudar uma regra

1. Escrever a regra de negócio e exemplos de aceitação/rejeição. Declarar se afeta projeto inteiro, passagem ou somente apresentação; definir a ação para NULL e o efeito sobre histórico.
2. Se for equivalência ou suspeita de nomes, editar o catálogo revisado conforme [QUARENTENA_E_IDENTIDADES.md](QUARENTENA_E_IDENTIDADES.md). Se for regra geral, alterar o módulo correspondente em `rules/`; incluir código estável em `EXCLUSION_REASONS` quando for exclusão. `talent_decision` deve retornar os motivos, nunca apagar a origem.
3. Acrescentar teste com caso válido, inválido, nulo e reinclusão após correção. Para tempo, testar limite do corte, retorno, empate e trecho inferido. Para duplicidade, testar tentativa de gravação e rollback no PostgreSQL local.
4. Incrementar `RULE_VERSION` quando houver mudança semântica. A publicação registra versão + hash de configuração/catálogo em `versao_regras` e conserva seu conteúdo em `meta_gold_rule_snapshot`. Mudança de estrutura também exige versão do contrato e migração explícita.
5. Executar Ruff, testes e integração **no PostgreSQL local**, com configuração separada. Nunca apontar fixtures de teste para a VPS.
6. Se mudar schema/contrato, executar `python scripts/generate_ddl.py` e `python scripts/generate_contract_docs.py`. Atualizar este PRD, dicionário, exemplos SQL e medidas afetadas.
7. Executar `sla-pipeline preview-gold` para calcular a proposta sobre a coleta existente sem gravar ou consultar Monday. Fazer backup e confirmar restore antes de mudar dados. Preparar comparação no mesmo corte: contagens, projetos excluídos, conjunto de IDs, horas e casos que mudaram por regra. Diferença precisa ser explicada, não apenas aceita porque o teste passou.
8. Publicar código no GitHub e conferir a imagem efetivamente implantada. `git push` não prova deploy. Reprocessar a Gold com o código correto quando necessário; validar antes de atualizar o Power BI.

Para desfazer: restaurar regra/catálogo anterior e reprocessar a partir da Bronze compatível, após verificar o corte. O replay normal usa o catálogo atual, não seleciona automaticamente uma versão histórica. Backup testado é a recuperação se a origem já não estiver disponível. Não reenumerar SKs ou apagar o histórico para corrigir grafia.

## 6. Armazenamento versão 3.0

PostgreSQL contém **somente gold_projeto_status**. A migração exclui fisicamente as outras 19 tabelas. Bronze/Prata/controle/revisões continuam como coleções privadas compactadas em `/app/runtime/pipeline_state_orcamento_18429499488.sqlite3`, usando os contratos abaixo. Não criar outro schema técnico.

O volume é obrigatório. `db/consumer.py` implementa publicação e migração; `db/checkpoint.py` faz gravação durável e recuperação por recibo. O recibo da geração publicada fica no comentário da Gold, atualizado no mesmo commit que suas linhas. PK, UNIQUE, CHECKs e índice único da última passagem são PostgreSQL; referências entre coleções são validadas em Python.

Inventário **lógico interno**, não inventário de tabelas do banco:

| Tabela | Informação e finalidade |
|---|---|
| `gold_projeto_status` | Saída única de indicadores: passagens elegíveis, tempos fechados e atributos |
| `quarentena_projeto` (coleção interna) | Fila de saneamento: projeto, nomes originais, motivos e versão; não entra nos KPIs |
| `bronze_monday_activity_log_raw` | Eventos originais; deduplicação por ID e reconstrução do histórico |
| `bronze_monday_item_snapshot_raw` | Cadastros/estado observados por item e data; origem de atributos e exclusões |
| `bronze_monday_board_schema_raw` | Configuração do quadro/mapeamentos por data; replay |
| `silver_monday_status_event_stg` | Eventos de status tipados, relacionados à origem |
| `dim_board` | Identidade/configuração relacional do quadro |
| `dim_item` | ID/SK e cadastro técnico do projeto; integridade referencial |
| `dim_status` | ID/SK, nome, ordem e classificação final dos status |
| `dim_person` | IDs dos usuários Monday e nomes disponíveis |
| `bridge_item_person` | Pessoa, projeto, coluna/papel e data de observação |
| `fct_item_status_interval` | Intervalos técnicos completos para reconciliar a Gold |
| `fct_item_status_daily` | Distribuição diária dos tempos; teste de reconciliação e base de evolução temporal |
| `fct_item_sla_summary` | Resumo técnico, início comprovado e status para transformação |
| `data_quality_issue` | Diagnósticos atuais por projeto/código, exclusões e pendências |
| `meta_column_mapping` | Quais colunas são extraídas/modeladas e sua origem |
| `meta_entity_mapping` | Correspondências de Marca/Talento e revisão humana |
| `meta_gold_rule_snapshot` | Conteúdo imutável de cada versão de regras aplicada |
| `etl_watermark` | Última coleta publicada com sucesso; controle incremental |
| `etl_run` | Auditoria de execução, reserva diária, resultado e métricas |

As views anteriores e as 19 tabelas auxiliares não são recriadas. `PostgresStore` é adaptador legado de migração/testes; a execução normal usa `ConsumerStore`. Quarentena/catálogo são exportados em CSV/JSON, conforme [guia de revisão](QUARENTENA_E_IDENTIDADES.md). Backup precisa incluir o checkpoint junto do dump PostgreSQL.

## 7. Aceite e consumo

Executar `validate`, `validate-gold` e `quality-profile`: conferem, respectivamente, a reconciliação técnica, a Gold contra intervalos/eligibilidade/corte e o contrato das 20 coleções internas e da publicação única. Leitura de validação PostgreSQL usa snapshot consistente para não misturar duas publicações.

Confirmar no banco: PKs sem duplicidade, UNIQUE `(board_id,item_id,ordem_etapa)`, uma última passagem por projeto, horas reconciliadas, corte único, nenhum projeto excluído presente e versão esperada. O [SQL de verificação](../sql/011_validar_consumo.sql) permite conferir pelo DBeaver sem acessar a VPS.

Atualizar o Power BI **após** a carga terminar, e não às 06h em ponto. A duração depende da API/rede. Usar `corte_local` no relatório para mostrar até quando os tempos valem. Para Projeto 360°, filtrar `item_id`, ordenar `ordem_etapa` e exibir qualidade junto das datas/horas. Para rankings, usar mediana, P95 e tamanho da amostra de passagens observadas encerradas. Não somar `tempo_desde_entrada_horas` repetido em cada linha: usar MAX por projeto ou uma agregação por projeto.

Limites conhecidos: retenção de logs do Monday, cadastro sem revisão integral, atributos históricos não reconstruídos, VPS provisória, sem alerta externo e sem homologação real no BigQuery. Constraints impedem duplicidade técnica; elas não provam que uma grafia ou informação preenchida na origem está correta. Esses limites acompanham os indicadores, em vez de serem ocultados com preenchimentos artificiais.
