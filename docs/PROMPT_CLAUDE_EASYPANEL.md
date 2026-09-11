# Conferência do EasyPanel — tabela única, aplicação 3.0

Use este roteiro sem criar bancos, tabelas, cron adicional, serviços pagos ou expor segredos.

```text
Confira a aplicação pipeline-orcamento no projeto banco_de_dados.
Fonte: CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO, main, Dockerfile da raiz.
Confirme o HEAD implantado e pacote sls-orcamento-pdd versão 3.0.1.
Uma réplica, stop-first, CMD padrão loop. Não executar daily/backfill para validar deploy.
Volume runtime persistente em /app/runtime, gravável por UID 10001. Não substituir/apagar o volume.
Preserve as credenciais, banco dados_globo e schema orcamento.
Schedule 0 6 * * *, America/Sao_Paulo. Confirmar loop_sleeping e próximo horário sem nova extração na subida.

Rode uma vez por comando, observando saída e exit code:
sla-pipeline check-db
sla-pipeline validate
sla-pipeline validate-gold
sla-pipeline quality-profile
sla-pipeline export-review
sla-pipeline health

check-db deve listar somente gold_projeto_status. Os 20 contratos no perfil são coleções internas, não tabelas PostgreSQL.
Se ainda houver 20 tabelas, NÃO faça DROP manual: confirme com o responsável que backup completo/restore foram testados, então execute migrate-single-table no container com o volume persistente. O comando transfere e verifica o estado antes de excluir as 19 tabelas.
Se só houver uma tabela mas faltar checkpoint, PARE a carga e restaure o par banco+runtime; não tente backfill para apagar o histórico faltante.

Informe versão observada, inventário físico, validações e próximo horário. Um agendamento futuro não prova execução já realizada. Falha de health deve ser reportada; não editar JSON para simular sucesso. Não ativar integração GitHub sem credencial configurada nem revelar URLs de deploy com token.
```
