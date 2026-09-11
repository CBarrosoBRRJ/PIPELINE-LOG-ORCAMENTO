# Prompt de conferência no EasyPanel — contrato 3.1

Use este texto para verificar o deploy; não crie outro cron nem tabelas auxiliares.

> No projeto banco_de_dados, app pipeline-orcamento, confira o HEAD atual da main do repositório CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO e a versão realmente executada (3.1.0 ou posterior validada). Não imprimir senhas, ambiente, tokens ou URL privada de deploy. Não contratar serviços.
>
> Configuração esperada: PG_SCHEMA=orcamento, PG_DB=dados_globo, host interno banco_de_dados_postgres-pipeline:5432; quadro 18429499488, status_19, INITIAL_STATUS_LABEL=Entrada, finais aprovados, timezone America/Sao_Paulo, cron 0 6 * * *, comando loop/CMD padrão, uma réplica, stop-first. Volume /app/runtime persistente e gravável por UID10001. Preserve os segredos existentes.
>
> O usuário aprovou exatamente duas tabelas públicas: orcamento.gold_projeto_status (passagens, campos do exemplo primeiro) e orcamento.pendencias_projeto (uma linha por projeto com motivos e correção). Não criar dimensões, Bronze/Prata, tabelas de controle nem outros schemas. No contrato atual, entrada e duração sem comprovação ficam NULL; o original permanece no checkpoint privado.
>
> Execute check-db, validate, validate-gold, quality-profile e health. Caso esteja no contrato antigo, não apague tabelas manualmente: seguir OPERATIONS.md com backup PostgreSQL+checkpoint e restore testado antes de migrate-consumption, seguido de replay e validações. Se já migrado/validado, não repetir backfill nem coleta.
>
> Confira que o serviço está ativo e que logs mostram loop_started e loop_sleeping para o próximo horário 06:00. Deploy/reinício não faz coleta imediata. Disparo futuro ainda não observado deve ser declarado como agendado, não como executado. Git push não comprova implantação: reporte commit, versão, inventário, contagens, corte, duplicidade, validações e agenda observados.
