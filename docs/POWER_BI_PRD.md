# PRD do Power BI — estudo de permanência e gargalos

Versão 1.0, 11/09/2026. Consulte [ACEITE_PROVISORIO.md](ACEITE_PROVISORIO.md) para o estado atual da carga e do deploy.

## Objetivo e base de consumo

Selecionar um projeto pelo ID original e mostrar quais etapas percorreu, quanto tempo ficou em cada visita e quanto acumulou em cada status. Comparar etapas para estudar padrões; **não há metas máximas de prazo** e o relatório não deve classificar atrasos neste momento.

Conectar ao PostgreSQL `dados_globo`, schema **`orcamento`**. Os schemas anteriores foram consolidados, com backup restaurado para conferência. Há somente um schema de negócio para este pipeline; `public` é o schema padrão do PostgreSQL.

A forma segura de acesso remoto (túnel/VPN/TLS ou regra de acesso restrita) será confirmada no EasyPanel. Não usar o hostname interno Docker no Power BI desta máquina. Usuário dedicado de leitura é a configuração prevista; não publicar credenciais administrativas em relatórios.

## Começar com três tabelas

| Tabela | O que contém | Papel no relatório |
|---|---|---|
| `dim_item` | Uma linha por projeto: ID, nome, quadro, status atual, ativo, datas e SK | Seletores de projeto e identificação para cruzar novas bases |
| `dim_status` | Uma linha por status: ID, nome, coluna, ordem, final e SK | Nome da etapa e classificação terminal |
| `fct_item_status_interval` | Uma linha por visita: início, fim/corte, duração, eventos, qualidade, atributos e IDs/SKs | Tabela central para medir permanência e trajetórias |

Crie somente estes relacionamentos ativos no modelo inicial:

| Lado 1 (único) | Lado N (várias visitas) | Filtro |
|---|---|---|
| `dim_item.item_sk` | `fct_item_status_interval.item_sk` | Dimensão → fato |
| `dim_status.status_sk` | `fct_item_status_interval.status_sk` | Dimensão → fato |

O SQL também aceita os IDs originais. No Power BI, use uma única chave por relação, não ID e SK simultaneamente. Nunca relacione pelo nome.

**Não ativar também `dim_status → dim_item.current_status_sk` nesse modelo:** status atual e etapa histórica são papéis diferentes. Esse caminho pode filtrar o passado pela situação atual. Se necessário, usar uma cópia de papel `dim_status_atual` para o filtro de situação atual, separada da dimensão histórica. Essa cópia seria do modelo BI, não uma tabela nova já criada no PostgreSQL.

Modelo dimensional: [orientação Microsoft](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema).

## O que cada uma das demais tabelas contém

| Tabela | Informação e uso |
|---|---|
| `dim_board` | Cadastro do quadro e origem. Usar quando houver vários quadros, controlando caminhos de filtro |
| `dim_person` | Identidade de pessoas, nomes e e-mails disponíveis |
| `bridge_item_person` | Atribuições por projeto, pessoa, coluna/papel e data de snapshot. Pessoas compartilhadas não tornam horas aditivas por pessoa |
| `bronze_monday_activity_log_raw` | JSON e metadados dos eventos capturados; evidência para auditoria |
| `bronze_monday_item_snapshot_raw` | Versão observada do item por dia, atributos e JSON original; várias datas são histórico legítimo |
| `bronze_monday_board_schema_raw` | Versão diária de colunas/status e mapeamento aplicado |
| `silver_monday_status_event_stg` | Mudanças de status normalizadas, identificadas pelo ID do evento |
| `fct_item_status_daily` | Minutos por projeto/status/dia local, somando visitas do mesmo dia. Não é uma fila histórica nem uma contagem de visitas |
| `fct_item_sla_summary` | Uma linha por projeto com situação atual, Entrada comprovada, lead time, finalização, idade da etapa e corte |
| `meta_column_mapping` | Coluna Monday → atributo analítico, tipo, presença e modelagem; catálogo para futuras expansões |
| `etl_watermark` | Corte confirmado que controla retomada incremental |
| `etl_run` | Histórico de cargas concluídas, horários e métricas |
| `data_quality_issue` | Diagnósticos atuais por item e código. Um item pode ter vários; não somar ocorrências como quantidade de projetos |

Há ainda quatro views comuns: `gold_project_status` (totais por item/etapa), `gold_status_metrics` (estatísticas e fila por etapa), `gold_status_bottlenecks` (ranking sem finais) e `gold_intervals_local` (intervalos com datas locais). Elas não são quatro novas cópias físicas dos dados. As views gerais incluem estimativas e visitas abertas.

Detalhamento completo: [PRD_ANALITICO.md](PRD_ANALITICO.md), [campos e tipos](CONTRATOS_DE_DADOS.md), [joins e exemplos](RELACIONAMENTOS_E_KPIS.md).

## Página 1 — projeto

Filtro: nome + `item_id`, para distinguir nomes iguais. Mostrar status atual, data/hora do corte e cobertura histórica.

Tabela de etapas: nome da etapa, visitas, horas observadas, horas estimadas e indicador de visita ainda aberta. Linha do tempo: cada intervalo separado, com início e fim/corte. Não agrupar a linha do tempo por status, pois esconde retornos.

Exemplo ilustrativo: Orçamento 5h, Revisão 2h, Orçamento 3h. O resumo apresenta Orçamento = 8h e duas visitas. Se a última visita está aberta, seu tempo é parcial até o corte.

Indicadores iniciais:

- Horas acumuladas: soma de `duration_hours`.
- Visitas: contagem de linhas de intervalos; para visitas comprovadas, filtrar `history_quality='observed'`.
- Horas observadas: soma somente de intervalos `observed`.
- Horas estimadas: soma de `initial_inferred` e `no_history_inferred`.
- Retornos observados por projeto/status: máximo(contagem de visitas observadas − 1, zero). Retorno não prova retrabalho por erro.

## Página 2 — processo

Comparar mediana, p95, média e volume de visitas **observadas e encerradas**, excluindo projetos com cadeia inconsistente ou divergência entre snapshot e logs. Usar a consulta 6 de [006_analise_projeto.sql](../sql/006_analise_projeto.sql) como definição da população. Exibir a quantidade de visitas/projetos da amostra.

Fila atual: itens ativos em status não terminal. Usar a consulta 7. Idade da fila deve distinguir início observado e desconhecido. Não misturar a duração final de quem já saiu com a idade parcial de quem continua aguardando.

Marca, Talento e demais atributos já materializados nos fatos podem ser filtros. A origem temporal desses atributos é indicada em `attribute_source`; versões anteriores à primeira observação não são comprovadas.

## Página 3 — qualidade e atualização

Mostrar corte, última carga concluída, projetos sem Entrada comprovada, projetos sem movimento disponível e registros estimados. Agrupar diagnósticos pela coluna **`code`**. A contagem de ocorrências é diferente da contagem distinta de `item_id` afetados.

NULL é desconhecido, não zero. `cliente` ausente na fonte não será preenchido artificialmente. O SLA total começa somente na Entrada comprovada; ausência dessa evidência não invalida visitas posteriores observadas.

## Relações adicionais sem duplicar medidas

Adicionar `fct_item_status_daily` ligado às mesmas dimensões de item/status e a um calendário por `dt`. Não relacionar diretamente os fatos nem somar suas horas entre si: representam o mesmo tempo em grãos diferentes.

Consultar o resumo por `item_sk` com relação um para no máximo um. Se importar o resumo em um modelo com múltiplos fatos, revisar os caminhos de filtro; não fazer joins físicos de resumo × visitas para depois somar lead time repetido.

Pessoas: incluir `snapshot_date` e coluna/papel da atribuição. Um join físico com duas pessoas duplica a visita; usar filtro por existência, ponte bem modelada ou uma medida explícita. Não somar totais por pessoa como se os projetos fossem exclusivos.

Nova base de outra área: conservar origem e IDs, verificar cardinalidade, agregar para uma linha por chave antes de cruzar medidas. O mesmo número de ID em sistemas diferentes não identifica automaticamente a mesma entidade. Não anexar novamente backups históricos à base consolidada.

## Regras e aceite

- Tempo corrido, com noites e finais de semana. Minutos / 60 = horas; horas / 24 = dias corridos.
- `status_to` é a etapa ocupada. `status_from` é a anterior.
- `is_open_interval=true`: fim representa corte de cálculo, não uma saída real; inclusive em etapa terminal.
- Finais vigentes: Encerrado, Declinado pelo Mercado, Declinado Internamente. Excluídos da fila, com regra de encerramento no resumo.
- Corte atual: início da execução diária. Agendamento às 06h de São Paulo. Não rotular como D+1 fechado à meia-noite.
- Validar ao menos um projeto com retornos, um com finalização e outro com lacuna histórica antes de compartilhar o relatório.
- Conferir somas antes/depois de relacionamentos e distinguir cobertura observada/estimada.
- Fonte de referência: somente `orcamento`. Não importar Bronze inteira no primeiro relatório sem necessidade.

O banco é provisório para estudo e futura migração ao BQ da Globo. Este documento orienta a construção; arquivo `.pbix`, gateway e atualização agendada do Power BI ainda não foram criados/testados.
