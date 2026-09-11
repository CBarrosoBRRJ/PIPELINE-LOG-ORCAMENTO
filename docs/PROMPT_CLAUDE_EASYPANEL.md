# Prompt para aplicar e conferir o deploy provisório

Copie o bloco abaixo para o Claude com acesso ao navegador. Preencher a evidência final com o resultado observado, sem presumir sucesso. O repositório possui webhook: push pode iniciar um deploy. Não é necessário criar novos serviços pagos, ferramentas de dados ou outro banco.

```text
Estamos finalizando um pipeline provisório Monday → PostgreSQL na Hostinger/EasyPanel, antes da migração para o BigQuery da Globo. Quero manter a operação simples e evitar infraestrutura desnecessária.

Repositório: https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO
Branch: main. Leia PRD.md, docs/ACEITE_PROVISORIO.md e docs/POWER_BI_PRD.md.
Atualização Gold 2.0: leia também docs/OURO_CONSUMO.md e docs/VALIDACAO_OURO.md. O código agora deve publicar orcamento.gold_projeto_status; as tabelas técnicas existentes permanecem. Não apagar schemas/tabelas, não executar backfill desnecessário e não modificar o catálogo de identidades sem revisão de negócio.
Aplicação: identifique o serviço do pipeline existente no projeto banco_de_dados; não confunda com o serviço PostgreSQL postgres-pipeline. O nome exibido pode estar traduzido como oleoduto-orcamento.

Faça, nesta ordem:

1. Confira a versão atualmente implantada e atualize o serviço existente para o HEAD de main. Não crie outro executor ou banco. Se o webhook já implantou a mesma versão, não faça redeploy desnecessário. Preserve segredos; não os imprima, não os copie para GitHub e não os inclua na resposta.

2. Nas variáveis da APLICAÇÃO, confira/aplique:
TARGET_DB=postgres
PG_DSN=   (vazio: uma DSN antiga não pode sobrescrever os campos separados)
PG_HOST=banco_de_dados_postgres-pipeline
PG_PORT=5432
PG_DB=dados_globo
PG_SCHEMA=orcamento
INITIAL_STATUS_LABEL=Entrada
FINAL_STATUS_LABELS=["Encerrado","Declinado pelo Mercado","Declinado Internamente"]
PREFERRED_TIMEZONE=America/Sao_Paulo
CRON_SCHEDULE=0 6 * * *
RUNTIME_DIR=/app/runtime
MONDAY_HTTP_TRANSPORT=requests
Preserve PG_USER, PG_PASSWORD, token Monday, MONDAY_BOARD_ID=18429499488 e MONDAY_STATUS_COLUMN_ID=status_19. Não use o hostname/porta públicos se a rede interna estiver disponível. Se houver PG_DSN preenchida, remova a precedência dela antes de validar o destino. Confirme a rede interna de fato; não remova/recrie redes do EasyPanel.

3. O comando da aplicação deve ser sla-pipeline loop, ou o ENTRYPOINT/CMD equivalente da imagem. Apenas UMA réplica e UM agendador para esse quadro. Não instalar cron adicional se o loop está ativo. A cada inicialização ele faz uma carga, depois roda diariamente às 06h de São Paulo (09h UTC). Isso não é fechamento D+1 à meia-noite.

4. Confirme volume persistente em /app/runtime e escrita pelo usuário da aplicação (UID 10001). Não apague volumes existentes. Confira logs da aplicação: loop_started, pipeline_end com status success e loop_sleeping com next_run correto. Em caso de erro, não expor a mensagem crua contendo SQL/credenciais e não afirmar que houve sucesso.

5. Pelo terminal DO CONTAINER DA APLICAÇÃO, execute um comando por vez:
sla-pipeline check-db
sla-pipeline validate
sla-pipeline quality-profile
sla-pipeline validate-gold
sla-pipeline health
O banco deve ser dados_globo e o schema orcamento. Se a configuração de finais estava incorreta e a carga atualizada ainda não terminou, aguarde ou execute sla-pipeline replay depois que o executor liberar o lock, seguido das validações. Não executar um backfill extra sem necessidade. Não criar testes fictícios no banco.

6. No PostgreSQL, confirme:
SELECT status_label,is_terminal FROM orcamento.dim_status WHERE is_terminal;
SELECT pipeline_name,last_run_utc,updated_at FROM orcamento.etl_watermark;
SELECT mode,start_at,end_at,status FROM orcamento.etl_run ORDER BY start_at DESC LIMIT 3;
SELECT count(*) AS passagens, count(DISTINCT item_sk) AS projetos, min(corte_utc), max(corte_utc) FROM orcamento.gold_projeto_status;
SELECT start_at,status,metrics->>'gold_rules_version' AS versao_gold FROM orcamento.etl_run ORDER BY start_at DESC LIMIT 3;
SELECT count(*)-count(DISTINCT interval_id) AS duplicadas FROM orcamento.gold_projeto_status;
Não tratar somente a presença da Gold como prova de deploy: houve publicação manual inicial. Uma execução remota posterior deve registrar gold_rules_version nos logs e em etl_run.metrics. Caso o webhook não tenha aplicado a main atual, implantar a versão atual e observar uma carga concluída. Não iniciar outro agendador.
SELECT code,COUNT(*) FROM orcamento.data_quality_issue GROUP BY code ORDER BY COUNT(*) DESC;
SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('rede_globo','orcamentos','orcamento');
O último resultado deve mostrar somente orcamento. Os três finais esperados são Encerrado, Declinado pelo Mercado e Declinado Internamente. Não limpar data_quality_issue nem preencher SLA desconhecido com zero. Os schemas antigos rede_globo e orcamentos já foram consolidados e retirados após backup com restauração testada. Não os recrie. Atualize consultas salvas e consumidores para orcamento.

7. Backup mínimo: confira a aba Cópias de Segurança do PostgreSQL e informe se existe backup recorrente, última execução e onde ele é armazenado. Já existem dumps locais fora da VPS; não afirmar que não há backup algum. Se houver destino externo já configurado, use-o para um backup diário com retenção curta (7 dias) e teste de disponibilidade. Não contratar armazenamento ou instalar serviços. Se não houver destino externo, registrar a pendência e manter o procedimento de dump/cópia externa do repositório. Backup no mesmo disco não protege contra perda da VPS.

8. Operação mínima: usar health e os logs já existentes. Se o painel tiver monitoramento/notificação já disponível na conta, configurar para atraso/falha sem criar uma plataforma nova e sem enviar mensagem de teste a terceiros. Caso contrário, registrar que ainda não existe alerta automático. Não configurar um healthcheck de reinício agressivo que provoque cargas em loop.

9. Conferir HTTPS no painel e restrição da porta PostgreSQL 5433. Antes de fechar acesso externo, validar um caminho de acesso pelo DBeaver/Python (túnel/VPN/TLS) ou regra restrita ao IP informado pelo usuário. Não bloquear o acesso atual sem uma alternativa funcional, não abrir a porta ao mundo, não inventar IP autorizado. Pedir somente o dado que faltar, sem solicitar senhas no chat. Não há autorização para enviar mensagens a outras pessoas ou contratar serviços.

Ao terminar, entregue: commit implantado, banco/schema, resultado de cada validação, próxima execução com fuso, finais configurados, estado do backup e acesso, e o que ficou pendente. Diferencie carga inicial confirmada de disparo futuro ainda não observado. Não use 'pode fechar tranquilo, amanhã roda garantido': agendamento é intenção até observar a execução. Esta é uma operação provisória, não infraestrutura corporativa definitiva. Não migre para BigQuery agora.
```
