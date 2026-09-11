> **Referência histórica anterior à arquitetura 3.0.** PostgreSQL agora contém somente `orcamento.gold_projeto_status`; tabelas auxiliares/relações SQL descritas abaixo foram retiradas. Não executar instruções antigas de criação/consulta dessas tabelas. Consulte o [PRD atual](../PRD.md) e a operação 3.0. Conceitos de identidade, nulabilidade e qualidade permanecem aplicáveis.

# Estado da base e operação provisória

Atualizado em 11/09/2026. Este documento prevalece sobre registros históricos de implantação. O objetivo é estudar permanência por etapa, antes da migração ao BigQuery da Globo; não há metas de prazo acordadas.

## Uma base, uma área

Banco PostgreSQL: **`dados_globo`**. Schema de negócio: **`orcamento`**, no singular. Um schema organiza tabelas dentro de um banco. `public` é o schema padrão do PostgreSQL, não uma segunda base do pipeline. Futuras áreas poderão ter seus próprios schemas e relações por IDs de origem/SKs, sem copiar estas tabelas.

O histórico de `rede_globo` foi reconciliado com `orcamentos`, preservando as identidades originais. Foram incorporados 4.541 snapshots de 10/09, uma versão de colunas e três registros de execução. Para chaves diárias presentes nos dois locais, prevaleceu a observação mais recente do destino; a cópia anterior completa permanece no backup.

Depois de restaurar o backup em PostgreSQL 17 isolado e conferir ausência de chaves históricas faltantes, retiramos `rede_globo` e renomeamos `orcamentos` para `orcamento`. A transação usou `DROP ... RESTRICT`: dependências externas impediriam a operação; não houve remoção em cascata de outras áreas. As contagens do destino permaneceram iguais durante a troca de nome.

Atualizados `.env` local, consultas e guias. No código, o alias temporário `PG_SCHEMA=orcamentos` resolve para `orcamento`, para não recriar a divisão antiga ao atualizar o executor. Configure explicitamente `PG_SCHEMA=orcamento` no EasyPanel. Não fazer rollback para a versão anterior usando a variável antiga. Consultas salvas fora deste repositório precisam trocar o prefixo para `orcamento.`.

## Correções e validação

- Corrigidos os três status finais: Encerrado, Declinado pelo Mercado e Declinado Internamente. O resumo foi recalculado; finais deixam de contar como fila.
- Reconstruídos os derivados usando todo o histórico disponível, no mesmo corte confirmado: **11/09/2026 16:26:18 UTC / 13:26:18 São Paulo**. Reprocessamento não é uma coleta nova da API.
- Base consolidada: 4.565 projetos, 4.561 ativos, 780 eventos, 9.102 snapshots diários, 5.342 visitas e 40.936 linhas de permanência diária; 16 tabelas físicas e quatro views comuns.
- O acréscimo de uma visita e uma linha diária em relação à primeira carga apresentada decorre da reconstrução com o histórico recuperado. Snapshots de dias distintos são versões legítimas, não duplicatas.
- `quality-profile` executado na imagem Docker: 16 tabelas, zero falhas críticas. `validate`: sucesso para 4.565 itens. Build Docker e Ruff concluídos. Testes: **68 aprovados**, incluindo integração em PostgreSQL local isolado; nenhum teste fictício foi inserido na VPS.
- O `loop` valida o horário diário completo, respeita o fuso e registra o tipo da falha sem imprimir a exceção crua. Configuração é lida ao iniciar; mudanças de variáveis exigem reinício/redeploy. Falha mantém o processo vivo e a próxima tentativa fica para o próximo ciclo diário; isso não equivale a uma notificação.

As contagens são evidência desse corte, não valores fixos para cargas futuras. A consistência técnica não comprova um histórico que a origem não disponibilizou. A fase de estudo deve separar visitas observadas de estimadas.

## Proteção contra duplicidades

Cada uma das 16 tabelas tem chave primária no seu grão. O contrato rejeita chaves duplicadas no lote; gravações usam upsert ou reconstrução transacional do quadro. IDs de eventos e visitas são estáveis, há exclusão mútua por quadro e o watermark só avança após commit completo. PKs, UNIQUE e FKs foram preservadas na consolidação. A chave primária impõe unicidade e não aceita nulos. [Referência PostgreSQL](https://www.postgresql.org/docs/17/ddl-constraints.html).

Auditoria real: **zero grupos de chaves duplicadas nas 16 tabelas**, 16 PKs, 8 UNIQUEs, 49 FKs e nenhuma constraint não validada. O replay preservou o hash do conteúdo das 16 tabelas e o watermark. A fila corrigida contém **967 projetos** no corte auditado.

Essa proteção cobre **duplicação pelas chaves definidas**. Não prometer “nunca haverá qualquer duplicidade”: itens copiados na origem com IDs diferentes e joins incorretos no Power BI exigem regras próprias. Duas pessoas ligadas ao mesmo projeto não autorizam somar suas horas duas vezes. Visitas de retorno à mesma etapa e snapshots em dias distintos são registros diferentes por definição.

Auditoria recorrente em leitura: [007_auditoria_orcamento.sql](../sql/007_auditoria_orcamento.sql). Reprocessar o mesmo corte deve preservar o conteúdo e não acrescentar linhas por repetição.

## Qualidade: não apagar diagnósticos

A carga consolidada possui 8.985 ocorrências de diagnóstico, não 8.985 projetos inválidos. Um projeto pode apresentar vários códigos. São lacunas de histórico ou observação que precisam acompanhar o indicador. Consulte a distribuição por `code`; a coluna não se chama `issue_type`.

| Código | Ocorrências | Interpretação / ação |
|---|---:|---|
| `inicio_entrada_nao_comprovado` | 4.415 | Não calcular total desde Entrada sem evento inicial |
| `status_sem_movimento` | 4.131 | Não apresentar permanência estimada como visita comprovada |
| `historico_inicial_inferido` | 431 | Separar o trecho inicial estimado dos eventos observados |
| `item_fora_snapshot_atual` | 4 | Preservar histórico; excluir da fila ativa |
| `item_sem_snapshot` | 3 | Há evidência histórica, mas faltam atributos/observação do item |
| `snapshot_status_divergente` | 1 | Snapshot e último evento não concordam; conferir origem/logs antes de afirmar idade atual |

Para a primeira comparação de etapas, a consulta 6 exclui projetos com cadeia inconsistente ou snapshot divergente. A evidência continua no banco; a exclusão da amostra é explícita. Resolver divergência requer conferir a origem ou obter eventos ausentes, não substituir um status por suposição.

Entrada inicial não comprovada continua com data e SLA total nulos. Nenhum outro status é promovido artificialmente a início. Coluna ausente na fonte, como Cliente no mapeamento atual, não recebe um valor inventado. Para comparar prazos de etapas, usar visitas observadas e encerradas, com cobertura da amostra explícita; para fila, usar projetos ativos em etapas não finais.

O [PRD Power BI](POWER_BI_PRD.md) explica tabelas, relacionamentos, filtros e indicadores. A falta de metas não impede estudar os tempos; impede classificar dentro/fora de um prazo acordado.

## O mínimo nesta fase

| Item | Estado e ação |
|---|---|
| Banco e dados consolidados | Corrigidos diretamente na VPS; consumir `dados_globo.orcamento` |
| Código e documentação | Conferir o commit em `main`; o painel deve implantar essa versão |
| Executor | O usuário instalou o serviço com webhook; confirmar versão e configuração pelo prompt abaixo. Não foi inspecionado diretamente nesta revisão |
| Horário | `loop`, carga ao subir e depois 06h São Paulo (09h UTC), uma réplica. Sem cron adicional |
| Corte | Início da execução. D+1 fechado à meia-noite permanece evolução futura |
| Backup | Dump externo à VPS antes da consolidação, com restore testado; também gerado dump final de `orcamento`. Agendamento recorrente externo ainda não confirmado |
| Falha/atraso | Logs e `health` implementados. Alerta externo não confirmado; aproveitar recurso já disponível no painel, sem plataforma nova |
| Acesso | Conferir HTTPS do painel e acesso restrito ao PostgreSQL. O acesso externo observado estava sem TLS; preservar acesso funcional do usuário ao configurar túnel/VPN/TLS/restrição |
| BigQuery e Power BI | Migração real ao BQ, arquivo PBIX, gateway e atualização agendada ainda não executados |

O alerta apresentado pelo usuário faz sentido como lista de itens a verificar, mas a afirmação de ausência total de backup ficou desatualizada. Já há cópias externas com restauração testada. Manter uma cópia recente e acesso controlado é útil mesmo no período provisório. Não contratar serviços, montar orquestrador novo, implantar SCD2 ou ampliar infraestrutura agora.

## Próximos passos do usuário

1. Copiar [PROMPT_CLAUDE_EASYPANEL.md](PROMPT_CLAUDE_EASYPANEL.md) para o Claude conferir o serviço existente, variáveis e versão implantada. Um push não comprova sozinho que o novo container ficou saudável.
2. No DBeaver, atualizar a conexão/árvore de schemas e abrir `dados_globo → orcamento → Tabelas`. Ajustar consultas salvas para o novo prefixo. Não criar outro banco.
3. Seguir [POWER_BI_PRD.md](POWER_BI_PRD.md), começando por item, status e intervalos. Validar alguns projetos com a equipe, expondo as lacunas da origem.

## Evidências locais de manutenção

Arquivos privados, fora do Git: `runtime/schema_consolidation.json`, `runtime/consolidation_restore_verified.json`, `runtime/final_database_audit.json` e dumps em `runtime/backups/`. A restauração de teste ocorreu sem portas publicadas, e o container temporário foi removido. Não compartilhar os dumps ou o `.env` no repositório público.
