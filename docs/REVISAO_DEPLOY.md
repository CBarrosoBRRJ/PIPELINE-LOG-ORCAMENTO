# Revisão do deploy informado em 11/09/2026

> Registro do diagnóstico anterior à correção. O estado atual e a consolidação em `orcamento` estão em [ACEITE_PROVISORIO.md](ACEITE_PROVISORIO.md).

Revisão somente leitura do PostgreSQL remoto e do código publicado em `origin/main` (commit `ea6c282`). O usuário apresentou o serviço no EasyPanel e a execução em `orcamentos`. Este registro não declara as pendências abaixo corrigidas e não substitui a configuração remota efetiva.

## Evidências confirmadas

- Banco `dados_globo`, schema novo `orcamentos`: 16 tabelas e quatro views comuns, não 20 tabelas físicas ou views materializadas.
- Execução `daily` concluída com sucesso: início em 11/09/2026 16:26:18 UTC, fim 16:28:21 UTC, 57 chamadas de API, 4.561 itens ativos, 4.565 itens na dimensão, 780 eventos, 5.341 intervalos e 40.935 registros diários.
- `orcamentos.etl_run` contém uma execução. Isso confirma a primeira carga; não comprova ainda o próximo disparo automático nem o webhook funcionando em todas as atualizações.
- A nova base contém todos os IDs de evento que existem na base anterior `rede_globo`.
- O código remoto adicionou `loop` e tornou esse comando o CMD do Dockerfile. Ele executa imediatamente ao iniciar e aguarda o próximo horário diário.

## Pendências para aceite

### Status finais divergentes — impacto nos indicadores

`orcamentos.dim_status` possui zero status com `is_terminal=true`. As regras anteriores configuravam Encerrado, Declinado pelo Mercado e Declinado Internamente como finais. Na nova base, 2.975 + 129 + 490 = 3.594 itens ativos nesses status são tratados como não terminais, afetando fila, finalização e lead time.

Conferir `FINAL_STATUS_LABELS` nas variáveis da aplicação e alinhar com a decisão vigente. Valor anterior:

```dotenv
FINAL_STATUS_LABELS=["Encerrado","Declinado pelo Mercado","Declinado Internamente"]
```

Após aplicar a configuração no executor, recalcular e validar o resumo/filas. Atualizar apenas as flags manualmente no banco seria insuficiente: o próximo lote pode sobrescrever e os resumos precisam ser recalculados.

### Dois schemas e snapshots anteriores

`rede_globo` continua existindo, com o corte anterior e os três finais configurados. `orcamentos` foi carregado separadamente: faltam nele 4.541 chaves de snapshots existentes na base anterior. Essas versões continuam preservadas em `rede_globo`; não houve comprovação de migração integral dos snapshots para o destino novo.

Definir o schema de consumo e reconciliar os históricos antes de desativar qualquer origem. Alinhar `.env` local, variáveis do executor, SQL, DBeaver/BI e documentação. Não apagar nenhum dos schemas durante essa decisão. As consultas salvas anteriormente usam explicitamente `rede_globo`.

### Horário e D+1

O `loop` interpreta os dois primeiros campos de `CRON_SCHEDULE` no `PREFERRED_TIMEZONE`; não usa o fuso do cron Linux. Com `0 6 * * *` e `America/Sao_Paulo`, executa às 06h locais. A proposta anterior era 03h locais, que nesse modo exigiria `0 3 * * *`.

Os outros campos da expressão cron são ignorados no código atual; ele suporta apenas um horário diário fixo. Falha no lote é registrada e a próxima tentativa fica para o próximo horário diário. Reiniciar/reimplantar executa uma carga imediatamente. Essas regras precisam de testes/documentação antes de ampliar o agendamento.

Agendamento diário não implementa fechamento D+1. O cálculo continua até o início da execução, sem reconstrução de um corte analítico à meia-noite.

### Qualidade e logs

Os 8.984 diagnósticos são: 4.415 sem Entrada comprovada, 4.131 sem movimentos disponíveis, 430 com trecho inicial inferido, quatro sem snapshot e quatro fora do snapshot ativo. Um item pode ter vários diagnósticos. Isso não equivale a 8.984 projetos inválidos ou erros de infraestrutura. A coluna correta para agrupamento é `code`, não `issue_type`.

```sql
SELECT code, COUNT(*) AS ocorrencias
FROM orcamentos.data_quality_issue
GROUP BY code
ORDER BY ocorrencias DESC;
```

O novo `loop` registra `str(loop_error)` sem a filtragem usada em outras partes do CLI. Exceções de drivers podem conter SQL/parâmetros; aplicar a mesma política de mensagens seguras antes de depender desses logs em produção. Isso é um risco identificado no código, não evidência de vazamento já ocorrido.

## Situação

Carga inicial confirmada e serviço apresentado pelo usuário. Aceite analítico/operacional condicionado ao alinhamento dos status finais, schema/histórico e horário, revisão dos logs e observação do próximo disparo automático. Configuração de segurança e conectividade interna não foi inspecionada diretamente no servidor nesta revisão.
