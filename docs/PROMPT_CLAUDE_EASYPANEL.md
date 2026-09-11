# Prompt — verificar o executor diário no EasyPanel

O push só implanta quando a integração está ativa. Houve observação de deploy automático desativado; confira o estado atual. Não presumir que um build verde comprova carga de dados.

Copie este bloco para o Claude no navegador:

```text
Confira o executor existente do pipeline no EasyPanel, sem criar serviços pagos ou outro banco.
Repositório: https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO
Branch: main. A versão atual do pacote e das regras deve ser 2.2.0.
Leia PRD.md, OPERATIONS.md, docs/PRD_ELT_REGRAS.md e docs/VALIDACAO_OURO.md.
Aplicação: banco_de_dados / pipeline-orcamento. Banco: postgres-pipeline.

1. Confira o HEAD do GitHub e o commit/imagem realmente implantados. Se já for a mesma versão, não redeploy por hábito. Confira fonte GitHub/main/Dockerfile correto e o estado do deploy automático. Se atualizar configuração, faça um único deploy para aplicar o conjunto.
2. Preserve os segredos sem imprimir ou copiar. Configuração da aplicação:
TARGET_DB=postgres
PG_DSN= (vazio, se usar os campos PG_*)
PG_HOST=banco_de_dados_postgres-pipeline
PG_PORT=5432
PG_DB=dados_globo
PG_SCHEMA=orcamento
MONDAY_BOARD_ID=18429499488
MONDAY_STATUS_COLUMN_ID=status_19
INITIAL_STATUS_LABEL=Entrada
FINAL_STATUS_LABELS=["Encerrado","Declinado pelo Mercado","Declinado Internamente"]
PREFERRED_TIMEZONE=America/Sao_Paulo
CRON_SCHEDULE=0 6 * * *
RUNTIME_DIR=/app/runtime
MONDAY_HTTP_TRANSPORT=requests
3. CMD padrão loop; uma réplica; zero downtime desligado (stop-first); /app/runtime persistente e gravável pelo UID 10001. Não instalar outro cron.
4. A versão nova NÃO executa carga ao subir. Deve registrar loop_started e loop_sleeping com o próximo horário das 06h São Paulo. Isso é o comportamento correto; não disparar daily/backfill para “ver se funciona”. A primeira carga agendada só é comprovada quando o horário chegar.
5. No terminal da aplicação, um comando por vez:
python -c "from sls_orcamento_pdd.rules import RULE_VERSION; print(RULE_VERSION)"
sla-pipeline check-db
sla-pipeline validate
sla-pipeline validate-gold
sla-pipeline quality-profile
sla-pipeline health
6. Verifique no banco a Gold publicada: corte único à meia-noite local, versão 2.2.0, zero IDs/ordens duplicados e nenhum projeto em comum com quarentena_projeto. Use sql/011_validar_consumo.sql. Confirmar que as quatro views antigas não existem; a migração explícita foi preparada no repositório. Não apagar as tabelas técnicas: elas são usadas pelo código atual.
7. Se a Gold ainda estiver em regra antiga, depois de confirmar a imagem nova e ausência de carga ativa, executar apenas sla-pipeline replay e repetir validate-gold/quality-profile. Replay não faz coleta nem avança watermark. Não alterar nomes no catálogo sem revisão.
8. Depois das 06h, etl_run deve mostrar uma linha mode=scheduled por data, com success e metrics.gold_cut_utc. Uma reserva running/failed não será repetida automaticamente no mesmo dia. Logs de erro não podem ser apresentados como sucesso.
9. Não mudar firewall, certificados, credenciais, banco ou volumes neste procedimento. Não contratar serviços. Reporte commit observado, versão de regras, próximo horário, resultado dos checks e se o disparo diário foi observado ou apenas agendado.
```
