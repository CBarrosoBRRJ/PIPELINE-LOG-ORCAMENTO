# Operação — executor 3.0 e PostgreSQL com uma tabela

## Destino e agenda

Banco `dados_globo`, schema `orcamento`, **somente `gold_projeto_status`**. Aplicação EasyPanel `pipeline-orcamento`, repositório `CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO`, branch `main`, Dockerfile na raiz, comando vazio (CMD loop), **uma réplica**, deploy stop-first. O volume `runtime` precisa estar montado em `/app/runtime`, gravável por UID 10001.

Ambiente: preservar segredos; `PG_SCHEMA=orcamento`, `PG_DB=dados_globo`, host interno `banco_de_dados_postgres-pipeline`, porta 5432; `MONDAY_BOARD_ID=18429499488`, `MONDAY_STATUS_COLUMN_ID=status_19`, `INITIAL_STATUS_LABEL=Entrada`, finais aprovados, `PREFERRED_TIMEZONE=America/Sao_Paulo`, `CRON_SCHEDULE=0 6 * * *`. Não imprimir o ambiente. PostgreSQL local de testes usa outro banco/schema e porta 55432.

`loop` espera o próximo horário futuro, sem carga na subida. A reserva diária tem ID determinístico e fica no checkpoint privado; uma tentativa por data, inclusive se falhar. Sem repetição automática ou catch-up após reinício. API/VPS indisponível exige diagnóstico e recuperação deliberada, não criação de outro cron.

O corte da Gold é meia-noite local, anterior à coleta das 06h. Watermark marca a coleta; não confundir timestamps. Atualizar Power BI após conclusão observada, exibindo `corte_local`.

## Migração autorizada de 20 para 1 tabela

1. Finalizar extrações/deploys concorrentes; confirmar volume persistente e versão 3.0.
2. Fazer pg_dump completo e testar pg_restore isolado. Este passo precisa ser observado antes da exclusão.
3. No **container da VPS** com o volume, executar `sla-pipeline migrate-single-table`.
4. O comando trava o quadro, exige inventário legado exato e um único quadro; lê todas as coleções consistentemente, valida contratos/referências/Gold e salva checkpoint durável.
5. Reabre o checkpoint e compara o conteúdo completo; cria cópia `.before_migration.sqlite3` no volume. Trava as tabelas e confirma que não mudaram durante a preparação.
6. Na mesma transação, remove FKs da Gold para tabelas retiradas, aplica CHECKs/índice de unicidade e remove **as 19 tabelas auxiliares**, sem CASCADE. Dependência externa desconhecida aborta tudo. Gold mantém suas linhas e chaves.
7. Grava o recibo no comentário da Gold e confirma a transação. Promove checkpoint e verifica inventário igual a uma tabela. Repetir a migração já concluída não exclui nada adicional.

Nunca apagar as 19 tabelas manualmente antes desse comando. Não aplicar antigos DDLs relacionais ou retornar à imagem 2.x: dependem de estruturas que deixaram de existir. A inicialização atual não recria auxiliares.

## Validação no executor

```bash
sla-pipeline check-db
sla-pipeline validate
sla-pipeline validate-gold
sla-pipeline quality-profile
sla-pipeline export-review
sla-pipeline health
```

`check-db` deve listar apenas `gold_projeto_status`. `validate` reconcilia coleções internas; `validate-gold` lê a Gold real e compara com o checkpoint e as regras; `quality-profile` inspeciona os 20 contratos lógicos (não 20 tabelas PostgreSQL). `health` confere Gold/checkpoint, watermark com execução bem-sucedida correspondente, atraso e tentativas posteriores. Tentativa antiga não agendada bloqueada exclusivamente por concorrência aparece como `warnings: [concurrent_attempt_rejected]`; seu registro não é apagado nem convertido em sucesso. Falha real posterior ou reserva diária sem sucesso mantém health em erro. Uma migração/replay não é nova extração Monday.

DBeaver/VS Code Python podem consultar a Gold diretamente. Use [SQL de validação](sql/011_validar_consumo.sql) e [trajetória de projeto](sql/006_analise_projeto.sql). Depois da remoção, clique Atualizar/F5 na pasta Tabelas e feche abas de objetos antigos. No Power BI, substitua consultas antigas pela única Gold.

## Estado privado e recuperação

Arquivo: `/app/runtime/pipeline_state_orcamento_18429499488.sqlite3`. Contém registros lógicos compactados de Bronze, derivados, identidades, quarentena, regras, watermark e execuções. Não é um serviço adicional nem requer acesso do Power BI. O comentário da Gold identifica qual geração desse arquivo foi publicada.

Antes de publicar, o checkpoint candidato é gravado com transação SQLite e sincronização FULL. A Gold inteira do quadro e o recibo mudam juntos em transação PostgreSQL. Após confirmação, o candidato é promovido. Se o processo morrer entre confirmação e promoção, o recibo permite recuperar o candidato correto no reinício. Se PostgreSQL reverter, o estado anterior continua válido. Um volume ausente/incompatível bloqueia a publicação.

Para backup do estado sem copiar um arquivo aberto de forma insegura:

```bash
sla-pipeline backup-state
```

O comando usa SQLite backup API sob o lock do quadro e grava `/app/runtime/backups/state_<UTC>.sqlite3`. Copiar esse artefato e o dump PostgreSQL para armazenamento externo controlado. Para um par restaurável: fora da janela de carga, pausar o agendador, gerar backup-state e pg_dump, guardar juntos com data/versão; só então retomar o agendador. Verificar o par em ambiente isolado com `validate-gold`. Não executar cron/carga no ambiente de restore.

Se perder o arquivo runtime, a Gold continua consultável, mas o pipeline deve parar até restaurar o checkpoint correspondente. **O dump PostgreSQL pós-migração sozinho não contém o histórico bruto.** Os dumps anteriores à migração preservam as antigas tabelas e permitem reconstruir o checkpoint em ambiente isolado. Não sobrescrever o banco atual com um restore sem conferir destino e plano de retorno.

Revisões de identidade: [guia](docs/QUARENTENA_E_IDENTIDADES.md). `replay` recalcula com fontes já guardadas, sem API e sem avançar watermark. `backfill` é exceção manual para buscar histórico disponível na API; nunca substitui backup do estado antigo.

## Limites operacionais

Não há alerta externo contratado nem backup externo recorrente comprovado. TLS/firewall/2FA seguem o aceite provisório. Nenhuma porta/permissão é aberta por esta migração. Para BigQuery será preciso migrar também evidências/controle ou redesenhar esse estado em armazenamento corporativo; não apenas copiar a Gold e descartar o histórico.

Referências técnicas: [DROP TABLE / RESTRICT](https://www.postgresql.org/docs/17/sql-droptable.html), [transações SQLite](https://www.sqlite.org/atomiccommit.html). O protocolo de recibo entre os dois armazenamentos é implementado e testado neste projeto; não é uma transação distribuída nativa.
