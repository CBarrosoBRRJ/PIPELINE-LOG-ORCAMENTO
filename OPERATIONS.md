# Operação — 3.1.0

## Destino, rotina e acesso

Banco `dados_globo`, schema `orcamento`, exatamente **gold_projeto_status e pendencias_projeto**. App EasyPanel `pipeline-orcamento`, GitHub `CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO`, main, Dockerfile na raiz, comando vazio (CMD loop), uma réplica, stop-first. Volume persistente `/app/runtime`, gravável pelo usuário pipeline (UID 10001).

Ambiente: preservar segredos; `PG_SCHEMA=orcamento`, `PG_DB=dados_globo`, host interno `banco_de_dados_postgres-pipeline`, porta 5432; `MONDAY_BOARD_ID=18429499488`, `MONDAY_STATUS_COLUMN_ID=status_19`, `INITIAL_STATUS_LABEL=Entrada`, finais aprovados, `PREFERRED_TIMEZONE=America/Sao_Paulo`, `CRON_SCHEDULE=0 6 * * *`. Não imprimir `.env` ou DSN. Testes usam PostgreSQL local separado, porta 55432.

O loop espera 06h; não coleta ao subir/reiniciar. Reserva determinística e persistente por data impede uma segunda tentativa automática, inclusive após falha. Não instalar outro cron. Se VPS/API estiver indisponível, diagnosticar e recuperar deliberadamente; o loop não faz catch-up automático.

D+1: execução de 12/09 às 06h fecha até 12/09 00:00, cobrindo o fim de 11/09. `corte_local` é fechamento dos tempos; `cadastro_referencia_utc` é quando atributos foram observados. Atualizar Power BI após conclusão da carga.

## Atualizar instalação anterior

1. Evitar extrações/deploys concorrentes. Confirmar `/app/runtime` persistente. Guardar versão atual.
2. Gerar backup do PostgreSQL e checkpoint correspondente; testar restore isolado antes da migração.
3. Implantar a aplicação 3.1.0 e, no container que possui o volume, executar `sla-pipeline migrate-consumption`.
4. O comando aceita o inventário legado completo ou a Gold única versão 3. Lê/reconcilia evidências, guarda checkpoint e cópia `.before_consumption_v4.sqlite3`, obtém locks exclusivos, reconfirma os dados e recria somente os dois contratos públicos em uma transação. Sem CASCADE: dependência externa desconhecida aborta tudo. Preserva dados internos, IDs, dono e grants da Gold; leitores SELECT também recebem SELECT na nova lista de pendências.
5. Executar `sla-pipeline replay` para reaplicar as regras atuais sobre a última coleta, sem nova chamada Monday e sem avançar o watermark.
6. Executar os comandos de validação abaixo. Confirmar dois nomes no inventário, horários, ausência de duplicatas e serviço ativo com `loop_sleeping` para a próxima execução.

`migrate-single-table` permanece alias de compatibilidade de `migrate-consumption`; o resultado atual são duas tabelas. `init-db` serve para instalação nova ou validação estrutural de instalação migrada; não recria auxiliares e bloqueia versão antiga sem migração. Não retornar a imagem 2.x/3.0 sobre o contrato 4.

## Validar e consultar

```bash
sla-pipeline check-db
sla-pipeline validate
sla-pipeline validate-gold
sla-pipeline quality-profile
sla-pipeline health
```

`check-db`: Gold + pendências somente. `validate`: tempos/referências lógicos. `validate-gold`: consulta as duas tabelas reais, compara com a projeção do checkpoint e reconcilia a Gold interna com a origem. `quality-profile`: 20 contratos internos, não 20 tabelas PostgreSQL. `health`: publicação, watermark, execução bem-sucedida correspondente, atraso e tentativas posteriores. Uma tentativa antiga não agendada rejeitada exclusivamente por concorrência aparece como aviso; falhas reais posteriores continuam bloqueantes.

SQL pronto: [validação](sql/011_validar_consumo.sql), [fluxo por projeto](sql/006_analise_projeto.sql). DBeaver: F5 na pasta Tabelas, reabrir a Gold e ordenar item_id/ordem_etapa. Power BI: [guia](docs/POWER_BI_PRD.md). As tabelas são saídas do pipeline: não corrigi-las com UPDATE manual. Nomes e cadastros se corrigem no Monday/catálogo.

## Checkpoint, backup e recuperação

Estado privado: `/app/runtime/pipeline_state_orcamento_18429499488.sqlite3`. Guarda Bronze, derivados, catálogo, quarentena, regras, watermark e execuções. O comentário da Gold registra a geração publicada (contrato 4). As duas tabelas e o recibo mudam no mesmo commit; a geração candidata já foi persistida com sincronização FULL. Reinício recupera a geração confirmada, inclusive após queda entre commit e promoção. Volume ausente/incompatível bloqueia cargas.

```bash
sla-pipeline backup-state
```

Esse comando usa SQLite backup API sob lock, produzindo `/app/runtime/backups/state_<UTC>.sqlite3`. Fora da janela de carga, com agendador pausado, guardar esse arquivo junto do pg_dump; copiar ambos para armazenamento externo controlado. Testar o par restaurado com `validate-gold`, sem loop/coleta no ambiente de teste. O dump atual sozinho não contém histórico bruto. Dumps pré-migração das antigas tabelas ainda são evidência de recuperação.

Revisões: `export-review` exporta CSV/JSON; `import-review --review-file` importa somente identidades revisadas. `replay` aplica o catálogo/algoritmo atual sem API. `backfill` é recuperação manual de histórico que a API ainda oferece, não substituto do backup. A tabela pendencias_projeto atualiza automaticamente em toda publicação da Gold.

Não há contratação nova. Alerta externo, backup externo recorrente e infraestrutura definitiva seguem as pendências do aceite provisório; BigQuery corporativo ainda requer implantação/reconciliação próprias.
