# Operação — 4.0.0 / GCP

Procedimento de implantação: [DEPLOY_GCP.md](docs/DEPLOY_GCP.md). Arquitetura vigente: [ARQUITETURA_GCP.md](docs/ARQUITETURA_GCP.md). BigQuery recebe somente sla_orcamento. Origem anterior: [migração somente leitura](docs/MIGRACAO_HISTORICO.md).

## Rotina GCP

O nome da área/projeto é PPD. O pacote Python passou a `sls_orcamento_ppd`; em instalações locais existentes, reinstale com `python -m pip install -e ".[dev]"` para atualizar o comando `sla-pipeline`. A imagem do Cloud Run precisa ser reconstruída para incorporar a alteração. Namespaces históricos de identidade permanecem iguais para preservar IDs/SKs e checkpoints.

Scheduler às 06h São Paulo invoca Cloud Run Job com daily, uma tarefa/retries zero. O Job usa ADC/service account, segredo Monday no Secret Manager e estado GCS. Não existe executor permanente/loop no aplicativo. `health`, `validate`, `validate-gold`, `quality-profile`, `export-review`, `import-review` e `replay` usam o estado remoto; runtime local não é durável nem necessário.

`sla-pipeline calendar --year 2026` imprime calendário BR PUBLIC e extras. expediente 10h–13h/14h–19h; seg-sex. Pendências e calendário ficam em generations/UUID/ junto da carga, e export-review salva relatório privado com URI. Para revisão, extrair a lista meta_entity_mapping, editar somente revisões aprovadas e importar JSON local ou gs://bucket/caminho; depois replay.

## Recuperação GCP

Falha de API antes de publicação conserva tabela e watermark; a reserva diária permanece (uma tentativa/dia). Corrigir causa. `replay` reaplica dados já capturados; nova coleta excepcional pode usar backfill manual, que lê toda a história ainda disponível e preserva a Bronze existente. Não apagar reserva para mascarar falhas. Próximo daily usa watermark anterior e recupera a janela ainda disponível na API.

Falha de comunicação BQ/GCS deixa journal pending: execute `recover`; ele resolve o mesmo job ID e valida tabela antes de promover. `recover` não consulta Monday. Se um load terminou em erro, a primeira recuperação registra a falha terminal e preserva active; nova recuperação verifica o estado anterior.

Processo morto pode deixar writer.lock. Primeiro pause Scheduler, confira/cancele a execução proprietária no Cloud Run e espere seu término. Execute `inspect-lock`; anote a geração. Só então `unlock --lock-generation NUMERO --execution-stopped`, seguido de `recover` e `validate-gold`. Unlock só remove a geração informada e não apaga checkpoints. Nunca liberar por idade da trava apenas.

`backup-state` salva um recibo control.json imutável em backups/. Este recibo referencia arquivos imutáveis em generations/: um backup externo completo deve copiar recibo + a geração de estado + artefato NDJSON + calendário/pendências correspondentes para armazenamento protegido. Um recibo isolado não substitui os dados referenciados. Bucket provisionado com versionamento, soft delete e prevent_destroy; sem TTL de estado. A política corporativa de cópia externa e retenção precisa ser implementada e testada.

Se um objeto foi removido, restaure sua versão exata pelo Cloud Storage. Se control.json sumiu e sla_orcamento existe, initialize bloqueia. Com todos os escritores parados, restaure o control.json mais recente cujo active/pending corresponda à tabela atual, execute recover e validate-gold. Não restaurar cegamente ponteiro antigo sobre tabela mais nova: fingerprint bloqueará. Para rollback integral, prefira restaurar estado e tabela em ambiente isolado a partir da mesma geração, reconciliar e só então realizar cutover aprovado. Não limpar bucket ou truncar tabela manualmente.

Logs estruturados ficam em Cloud Logging e relatórios JSON em reports/. Alertar falha de Job e ausência de fechamento; Scheduler com resposta 2xx não comprova sucesso da extração. Publicação só fica pronta quando BQ job e reconciliação concluem. Credenciais, payloads e .env nunca devem ir para logs.

## Atualização de precisão

Após publicar a imagem com horas arredondadas a três casas, executar `replay` e `validate-gold` para atualizar a tabela a partir do histórico privado, sem nova coleta Monday. Preservar estado e conferir pending/execuções antes de publicar. Não executar init-db nem backfill para esta alteração.
