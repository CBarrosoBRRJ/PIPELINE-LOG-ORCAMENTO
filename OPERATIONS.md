# Operação e implantação na VPS

## Atualização Gold 2.0

`daily`, `backfill` e `replay` agora publicam também `gold_projeto_status`, com catálogo `meta_entity_mapping` e snapshots imutáveis `meta_gold_rule_snapshot`. A migração é aditiva; não remover as tabelas antigas nem resetar watermark. O Power BI novo importa uma tabela. Consulte [o contrato de consumo](docs/OURO_CONSUMO.md) e [a validação](docs/VALIDACAO_OURO.md).

Após atualizar o código, executar `sla-pipeline replay` se for necessário publicar sem consultar a API/avançar corte; depois `sla-pipeline validate`, `sla-pipeline validate-gold` e `sla-pipeline quality-profile`. Com a carga diária atualizada, isso ocorre automaticamente. Não disputar execução com o loop; ele usa lock por quadro.

O replay não comprova deploy do agendador. Conferir a versão no painel e os campos `gold_rules_version`, `gold_projects` e `gold_excluded_projects` nos logs/`etl_run.metrics` da execução remota. Um executor antigo não atualiza a Gold. Para corrigir identidades, editar o catálogo conforme o guia e reprocessar fora de uma carga em andamento; não editar linhas da Gold manualmente.

## PostgreSQL existente na VPS (configuração atual)

Banco `dados_globo`, schema **`orcamento`**, PostgreSQL 17.11. Existe apenas uma área de dados deste pipeline. Os nomes anteriores foram consolidados com backup testado; não criar outro banco.

A aplicação existente no EasyPanel executa `sla-pipeline loop`: carga ao iniciar e depois às **06h America/Sao_Paulo**, com `CRON_SCHEDULE=0 6 * * *`. Manter uma réplica, sem cron adicional. O corte é o início da carga, não meia-noite/D+1.

Siga [o prompt de conferência do EasyPanel](docs/PROMPT_CLAUDE_EASYPANEL.md) e [o aceite provisório](docs/ACEITE_PROVISORIO.md). Configure `PG_DB=dados_globo`, `PG_SCHEMA=orcamento`, host interno e porta 5432 na aplicação; preserve as credenciais. A compatibilidade temporária do código converte `PG_SCHEMA=orcamentos` para `orcamento`, mas o painel deve usar o nome correto explicitamente. Não retornar a um código anterior à consolidação com a variável antiga.

Para comandos avulsos com Compose remoto, mantenha `COMPOSE_FILE=compose.remote.yaml`, `PG_DSN` vazio e rede interna real configurada. Esse Compose não cria um banco. Não executar carga manual enquanto a aplicação já está processando; o lock por quadro protege contra concorrência.

Para acesso externo, a conexão testada estava sem TLS. A execução no servidor deve usar a rede interna; acesso remoto administrativo/BI requer túnel/VPN ou configuração TLS validada. `PG_SSLMODE=prefer` permite conexão sem TLS; `verify-full` exige endpoint/certificado compatíveis. As chaves `VPS_PG_*` são referências de endpoints, e `LOCAL_PG_*` preservam a origem: apenas `PG_*`/`PG_DSN` controlam o destino ativo.

## Preparar uma instalação nova com PostgreSQL próprio

Esta seção é uma alternativa para ambiente novo, com `COMPOSE_FILE=compose.yaml`. Não se aplica ao banco existente acima.

### Preparação

Pré-requisitos: Linux, Docker Engine com Compose v2, acesso HTTPS à API Monday, espaço para volume PostgreSQL, backups e snapshots. Reserve inicialmente 2 vCPU/4 GB RAM e acompanhe o crescimento. O MVP reconstrói os derivados do board a cada execução; a extração de eventos é incremental.

1. Coloque o projeto em `/opt/sls_orcamento_pdd` (incluindo o `.env`, por canal seguro). Use somente um `.env`. Não copie `.venv`, `runtime` ou senhas para Git.
2. Escolha `PG_USER`, `PG_PASSWORD` forte e `PG_DB=sla_workflow` antes de criar o volume. O Compose cria automaticamente o banco e o usuário na primeira inicialização.
3. Mantenha `PG_DSN` vazio no deploy com Compose. Dentro do container, `PG_HOST=postgres` e `PG_PORT=5432` são definidos pelo Compose; na máquina host, o `.env` usa a porta externa 55432.
4. O estado do container usa o volume Docker `runtime_data`, com permissão do usuário da aplicação:

```bash
cd /opt/sls_orcamento_pdd
chmod 600 .env
mkdir -p runtime logs
docker compose up -d postgres
docker compose --profile job build pipeline
docker compose --profile job run --rm pipeline discover
docker compose --profile job run --rm pipeline backfill
docker compose --profile job run --rm pipeline validate
docker compose --profile job run --rm pipeline health
```

O PostgreSQL usa volume persistente. **Não execute `docker compose down -v`**: isso remove o volume. Trocar a senha no `.env` depois de criar o volume não altera a senha dentro do PostgreSQL; faça rotação via `ALTER ROLE` e então atualize o arquivo.

## Alternativa: cron Linux (não usar junto com o loop)

```bash
bash scripts/setup_cron.sh
crontab -l
```

Para instalações que escolherem cron em vez do loop, o script instala uma única linha marcada `sls_orcamento_pdd`, preservando outras tarefas. `CRON_SCHEDULE="0 6 * * *"` significa 06h **no timezone do servidor**. Confira com `timedatectl`; em servidor UTC, 06h corresponde a 03h em São Paulo. `PREFERRED_TIMEZONE` controla as datas analíticas e não modifica o relógio do cron. O usuário do cron precisa de acesso ao Docker e ao diretório `logs`.

`run_daily.sh` aplica `flock` e o PostgreSQL aplica advisory lock por board. O lock de banco é liberado automaticamente se a sessão cair. Agende um backfill periódico separado, por exemplo semanal, caso seja necessário recuperar eventos publicados com atraso maior que a sobreposição.

## Conferir cada execução

- No EasyPanel, logs da aplicação; no modo cron, `logs/daily.log`: eventos, duração e contagens.
- `/app/runtime/status_<board_id>.json` no volume `runtime_data`: último resultado, gravado por substituição atômica. Em execução Python local, fica na pasta `runtime/`.
- `orcamento.etl_run`: execuções bem-sucedidas e respectivas métricas.
- `orcamento.etl_watermark`: corte do último commit completo.
- `orcamento.data_quality_issue`: ausência de histórico, status vazio, divergências, itens ausentes.

Para ler o estado do container: `docker compose --profile job run --rm --entrypoint cat pipeline /app/runtime/status_18429499488.json`. Os estados de execuções Python locais e Docker ficam em locais distintos; use um único modo no cron.

No `loop`, falhas ficam nos logs/arquivo de estado e o processo espera o próximo ciclo diário. Isso não dispara notificação externa; `health` deve ser acompanhado. Em comando avulso, falha retorna código não zero. Não são gravadas como sucesso no banco. Monitore exit code e idade do arquivo; `health` falha após `RUN_WINDOW_HOURS + 2` horas ou se o último status não for sucesso. As contagens de inseridos são calculadas contra o estado anterior sob lock; `upserted_existing_events` conta IDs já existentes, não necessariamente valores alterados.

Copie `scripts/logrotate.conf` para `/etc/logrotate.d/sls-orcamento-pdd`, ajustando caminho e `su` ao usuário que executa o cron. Backups não substituem retenção dos logs da origem.

## Backup e recuperação

`scripts/backup.sh` detecta o Compose selecionado: banco próprio usa o serviço `postgres`; banco existente usa o serviço opcional `backup` (cliente PostgreSQL 17, somente `PG_SCHEMA`). O dump só recebe o nome final após sucesso; arquivos `.partial` indicam backup incompleto. `PG_DSN` deve estar vazio no modo remoto.

Para o modo remoto: `bash scripts/backup.sh`. Restaure pelo painel ou com `pg_restore --no-owner --no-privileges` conectado a um **banco vazio separado**, usando um cliente da mesma versão ou mais recente. Não restaure sobre `dados_globo` para testar.

O exemplo de restore abaixo é exclusivo do modo com banco próprio (`compose.yaml`):

```bash
bash scripts/backup.sh
# Para copiar dados locais para a VPS, transfira o .dump por canal seguro.
# Restaurar SOMENTE em banco novo/vazio; sem --clean e sem DROP:
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' < runtime/backups/ARQUIVO.dump
docker compose --profile job run --rm pipeline validate
```

Teste a restauração num banco separado e mantenha uma cópia fora da VPS. Após restaurar, rode `daily`; o watermark restaurado controla o ponto de retomada.

## Troubleshooting

| Sintoma | Ação |
|---|---|
| Monday 401/403 | Verifique o token no `.env` e acesso ao board; não cole token em logs |
| Coluna não encontrada | Execute `discover`; ajuste `MONDAY_STATUS_COLUMN_ID` ou overrides |
| Títulos ambíguos | Defina o ID em `BUSINESS_COLUMNS_OVERRIDE` |
| Timeout/TLS no Windows | Use `MONDAY_HTTP_TRANSPORT=curl`; mantenha certificados verificados |
| Complexity/rate limit | A retentativa respeita espera indicada; reduza tamanho de página se persistir |
| Contagem de itens mudou durante leitura | Reexecute; snapshot é paginado, a origem não oferece transação de leitura |
| Falha após ler páginas | Watermark e tabelas ficam no último commit; reexecute o mesmo comando |
| Correção da lógica sem reler API | `replay`, seguido de `validate` |
| Histórico anterior ausente | Verifique criação/cópia do board, retenção do plano e permissões; não inferir transições como fatos |
| Cliente nulo | Coluna não existe no quadro atual; configure uma fonte quando disponível |
| Falha ao gravar runtime | Confirme o volume `runtime_data` e proprietário UID 10001 |

## Power BI e credenciais de leitura

No modo local com banco próprio, o banco está publicado apenas em loopback. Na VPS atual existe porta externa; restrinja o acesso ao configurar o servidor. Use túnel SSH/VPN ou gateway perto da VPS para o Power BI. Para teste via túnel: `ssh -L 55432:127.0.0.1:55432 usuario@VPS`. O comando precisa do host/usuário reais; ajuste as portas ao endpoint real do banco.

Crie um papel dedicado de leitura ao configurar BI; conceda `USAGE ON SCHEMA orcamento`, `SELECT ON ALL TABLES IN SCHEMA orcamento` e privilégios padrão de SELECT para objetos futuros. Não use a conta administrativa do ETL no compartilhamento do relatório. O pipeline trata pessoas como atribuições do projeto, não como prova de quem causou a demora.


## Evolução de contratos e nulos

Antes de uma atualização de obrigatoriedade, rode `quality-profile` com o código novo e faça backup. Campos requeridos passam a NOT NULL em `init-db`; uma linha legada incompatível aborta a migração sem inventar um preenchimento. O contrato portátil também verifica tipo, identidade, domínio e duração antes de publicar. Depois, `replay` aplica a limpeza a derivados no mesmo corte; `validate` confere durações. A Bronze continua preservada.

Regenerar artefatos ao alterar contrato/metadata: `python scripts/generate_ddl.py` e `python scripts/generate_contract_docs.py`. Leia [ARQUITETURA_E_GOVERNANCA.md](docs/ARQUITETURA_E_GOVERNANCA.md). O perfil materializa uma tabela por vez em memória no MVP; adequar para validação por lote/agregação SQL em volumes maiores.
