# PRD analítico — permanência por etapa e gargalos

Versão 1.0 — 11/09/2026. Complementa o [PRD principal](../PRD.md), que permanece como referência de arquitetura e manutenção. Banco atual: `dados_globo`, schema `orcamento`.

## Pergunta principal e critério de sucesso

Ao selecionar o projeto X pelo `item_id` original do Monday, apresentar a sequência de etapas, entrada e saída de cada visita, duração por visita e duração acumulada por status. Se o projeto retornou ao mesmo status, exibir as visitas separadas na linha do tempo e somá-las no resumo. Distinguir o último intervalo em andamento dos encerrados e identificar os trechos estimados por ausência de logs.

Exemplo ilustrativo: Entrada 2h → Orçamento 5h → Aprovação 3h → Orçamento 4h. O resumo mostra Orçamento = 9h e duas visitas. Se a segunda visita ainda estiver aberta, as 4h representam tempo até o corte da carga, não a duração final dessa visita.

**Decisão confirmada em 11/09/2026:** estamos em fase de estudo, sem prazos máximos acordados. O produto deve medir tempos reais e subsidiar padrões futuros; não classificar atrasos nesta fase.

**Tempo medido e meta de SLA são conceitos separados.** O pipeline já mede permanência. Para informar cumprimento de SLA, faltam metas acordadas por etapa, unidade, calendário, vigência e regra para retornos. Não existe tabela de metas nem classificação de cumprimento implementada atualmente. Não inventar um limite de prazo.

Guia de correlação entre bases, joins e montagem no Power BI: [RELACIONAMENTOS_E_KPIS.md](RELACIONAMENTOS_E_KPIS.md).

## Como consultar agora no DBeaver

1. Na conexão `dados_globo`, abra um editor SQL. As consultas usam `orcamento` explicitamente, mesmo que a barra superior mostre `public`.
2. Abra [sql/006_analise_projeto.sql](../sql/006_analise_projeto.sql). Execute uma consulta por vez.
3. Na consulta 1, informe parte do nome em `:termo`. Copie o `item_id` encontrado **sem pontos de formatação numérica**.
4. Nas consultas 2 a 5, informe esse ID em `:item_id`. Se o editor não estiver configurado para parâmetros nomeados, substitua `:item_id` pelo número e `:termo` por um texto entre aspas simples.
5. A consulta 2 mostra a linha do tempo; a 3 resume por etapa; a 4 mostra o estado atual; a 5 explica lacunas. Use as quatro em conjunto.
6. As consultas 6 e 7 comparam etapas e filas; a 8 informa o corte da base.

`dim_item` é o cadastro do projeto. Ela não possui uma coluna para cada etapa: as visitas ficam em linhas na tabela de intervalos. Esse formato acomoda novos status e permite relacionar outras bases pelo mesmo ID.

## Regras de interpretação

| Regra | Consequência na análise |
|---|---|
| O status ocupado é `status_to`/`status_id` do intervalo | `status_from` é a etapa anterior, não a etapa cuja duração está sendo medida |
| Tempo corrido, em minutos e horas | Inclui noite, feriados e finais de semana; dias corridos = horas / 24 |
| SLA total começa na primeira Entrada comprovada | Ausência desse evento deixa o total nulo; tempos disponíveis das demais etapas continuam analisáveis |
| Retornar a Entrada não reinicia o SLA total | Retornar a qualquer etapa cria outra visita, quando há transição real |
| Evento sem mudança de status | Preservado nos eventos, mas não reinicia a permanência |
| Último intervalo usa o corte da execução | `is_open_interval=true` significa que não há saída registrada; `status_end_utc` é o limite de cálculo |
| Status final continua tendo permanência | O resumo encerra o lead time em um final configurado e comprovado; a permanência no final continua registrada |
| Reabertura de projeto | O lead time volta a contar desde a Entrada inicial, sem descontar o período intermediário no status final |
| `summary.open_interval` e `interval.is_open_interval` têm sentidos diferentes | No resumo, indica status não terminal; na tabela de visitas, ausência de próxima transição, inclusive em status terminal |
| Item fora do snapshot atual | Fica fora da fila ativa; isso não prova exclusão nem informa a data de saída do quadro |
| Datas persistidas em UTC | Consultas convertem para `America/Sao_Paulo`; não converter duas vezes no BI |
| Snapshot diário substituído na reexecução do mesmo dia | Não equivale a um registro de todas as alterações de atributos dentro do dia |

## Qualidade e cobertura histórica

`history_quality` em **cada intervalo**:

- `observed`: início baseado em evento disponível. Verificar também os diagnósticos de cadeia; o rótulo não garante ausência de logs faltantes no meio do histórico.
- `initial_inferred`: etapa anterior ao primeiro evento estendida até a criação do item como estimativa. A data real de entrada nessa etapa não foi comprovada.
- `no_history_inferred`: não há transições disponíveis; status observado no snapshot aplicado desde a criação como estimativa. Não prova quais outras etapas o projeto percorreu.

Um item sem Entrada comprovada pode ter visitas posteriores observadas e úteis para comparar etapas. Nulo significa desconhecido, nunca zero. A qualidade no resumo corresponde ao primeiro intervalo; para avaliar uma visita específica, use a qualidade da tabela de intervalos.

Histórico anterior à criação/cópia do quadro ou indisponível na API não pode ser recriado pelo pipeline. Para completá-lo, seria necessária outra fonte histórica, com IDs e timestamps verificáveis. Não preencher a trajetória ideal do processo como se fosse a trajetória real de cada projeto.

Para KPIs de duração final por visita, a consulta 6 usa somente visitas observadas, encerradas, com evento de saída e sem diagnóstico de cadeia inconsistente no projeto. Essa é uma amostra do histórico disponível: projetos ainda em andamento e sem evidência ficam fora e devem ter sua cobertura apresentada. O ranking não prova causalidade nem mede esforço efetivo de trabalho.

## Dicionário das 16 tabelas

Grão significa o que uma linha representa. As chaves abaixo são as chaves primárias naturais/técnicas atuais; dimensões também possuem SK determinística única. Relacionamentos completos estão em [RELATIONAL_MODEL.md](RELATIONAL_MODEL.md).

| Tabela | Uma linha representa / chave | Conteúdo e uso |
|---|---|---|
| `dim_board` | Um quadro / `board_id` | Nome, criação, atualização e `board_sk`. Delimita a origem da análise |
| `dim_item` | Um elemento Monday / `item_id` | Nome, quadro, criação, atualização, status atual, ativo, última observação e `item_sk`. Cadastro para procurar o projeto e cruzar novas bases |
| `dim_status` | Um status da coluna/quadro / `status_id` | Rótulo, índice/ordem, coluna, cor, indicador de final e `status_sk`. A ordem cadastrada não representa a trajetória real do projeto |
| `dim_person` | Uma pessoa / `person_id` | Nome, e-mail quando disponível e `person_sk`. Identidade para relacionar atribuições; não comprova quem causou uma demora |
| `meta_column_mapping` | Uma coluna do quadro / `board_id, column_id` | ID, título, tipo, atributo analítico, extraída/modelada/presente e descoberta. Mapeia a origem de cada coluna usada pelo pipeline; colunas não modeladas continuam no JSON bruto |
| `bronze_monday_activity_log_raw` | Um evento capturado / `event_id` | Item, quadro, status anterior/posterior, instante do evento, timestamp original, origem do timestamp, ingestão e JSON bruto. Evidência para auditoria e reprocessamento; escopo extraído é a coluna de status configurada |
| `bronze_monday_item_snapshot_raw` | Um item em uma data de snapshot / `board_id, item_id, snapshot_date` | Estado observado, status, atributos de negócio, pessoas, hora da observação e JSON completo do item. Base para enriquecimento e evolução de colunas |
| `bronze_monday_board_schema_raw` | Uma versão diária do quadro / `board_id, snapshot_date` | JSON do schema, mapeamento aplicado e horário de coleta. Ajuda a investigar colunas e status existentes naquela coleta |
| `silver_monday_status_event_stg` | Um evento de status normalizado / `event_id` | Item, quadro, status de destino, nomes de origem/destino, instante UTC e origem do timestamp. Consulta de transições, antes da montagem de visitas |
| `bridge_item_person` | Uma atribuição de pessoa por coluna e dia / `item_id, person_id, source_column_id, snapshot_date` | Papel, coluna fonte, IDs e SKs. Relação muitos-para-muitos; um join sem controlar a multiplicidade pode duplicar horas |
| `fct_item_status_interval` | Uma visita contínua a uma etapa / `interval_id` | Entrada, fim/corte, minutos, horas, aberto, eventos que iniciam/encerram, IDs/SKs, atributos e qualidade. **Tabela principal do projeto** |
| `fct_item_status_daily` | Um item/status/dia local / `board_id, dt, item_id, status_id` | Minutos alocados a cada dia e atributos. Soma visitas do mesmo status naquele dia; não conta visitas e não preserva a flag de qualidade por intervalo |
| `fct_item_sla_summary` | Um resumo atual por projeto / `item_id` | Status atual, Entrada comprovada, finalização, lead time, idade da etapa atual, ativo, qualidade e corte. Não substitui a linha do tempo |
| `etl_watermark` | Um checkpoint do pipeline / `pipeline_name` | Último corte concluído, referência de evento/cursor e atualização. Controla retomada; não é dado de negócio |
| `etl_run` | Uma execução concluída com sucesso / `run_id` | Modo, início, fim e métricas em JSON. Falhas são registradas no log/arquivo de estado; não procurar aqui um inventário completo de tentativas malsucedidas |
| `data_quality_issue` | Um diagnóstico atual com ID estável / `issue_id` | Projeto, código, detalhe e detecção. Reconstruído na carga; não é um histórico imutável de incidentes |

As SKs são UUIDv5 determinísticas e adicionais aos IDs originais. Não são versões SCD2. Dimensões representam o estado mais recente; o histórico de atributos disponível vem dos snapshots. Preserve IDs e SKs ao migrar para BigQuery.

## As quatro views existentes

| View | O que entrega | Cuidados |
|---|---|---|
| `gold_project_status` | Minutos/horas totais e número de visitas por projeto/status | Inclui trechos estimados e abertos. Join com dimensões para nomes; consulta 3 separa evidências |
| `gold_status_metrics` | Contagem de intervalos, tempo acumulado, média, mediana, p95 e fila atual por status | Estatísticas por visita, incluindo abertas e inferidas; não são automaticamente KPIs de duração final comprovada |
| `gold_status_bottlenecks` | Ranking de horas acumuladas e tamanho da fila, sem finais | Grande volume pode gerar muitas horas mesmo em etapa rápida. Compare com mediana/p95 e volume |
| `gold_intervals_local` | Intervalos com colunas adicionais de datas locais | Conserva UTC e qualidade; a data final de intervalo aberto ainda representa o corte |

Views são consultas salvas, não novas cópias físicas de dados. No DBeaver, ficam na pasta **Views**, separada de **Tabelas**.

## KPIs possíveis e contratos de cálculo

| Indicador | Cálculo / fonte | Leitura correta |
|---|---|---|
| Permanência do projeto por etapa | Soma de `duration_hours` agrupada por item/status | Responde à pergunta principal; separar observado e estimado e sinalizar intervalo aberto |
| Trajetória do projeto | Intervalos ordenados por início, fim e ID | Mostra visitas e retornos; eventos com mesmo instante podem exigir consulta ao timestamp bruto para desempate exato |
| Visitas e retornos | Contar intervalos por item/status; retornos = máximo(visitas − 1, 0) | Para indicador comprovado, contar visitas observadas. Retorno não prova retrabalho por erro |
| Mediana por etapa | Percentil 50 da duração de visitas observadas encerradas | Tempo típico da amostra; informar número de visitas e período/coorte |
| p95 por etapa | Percentil 95 da mesma população | Mostra a cauda de espera; pouco estável com amostra pequena |
| Média por etapa | Soma de duração / número de visitas elegíveis | Projetos com várias visitas pesam mais. Para média por projeto, agregar primeiro item/status |
| Fila atual | Contar itens ativos no status atual não terminal | Estado do último snapshot, não fila histórica à meia-noite |
| Idade atual da fila | Corte menos início da visita atual reconciliada | Priorizar observados; exibir quantidade com idade desconhecida |
| Participação da etapa no tempo | Horas da etapa / horas de todas as etapas elegíveis | Mesma população e qualidade no numerador/denominador; não confundir com percentual de esforço |
| Fluxo concluído da etapa | Contagem de visitas com evento de saída no período | Definir fuso e período por data de saída; contar projetos distintos é outro KPI |
| Horas por dia | Soma de `minutes_in_status` / 60 em `fct_item_status_daily` | Distribuição de permanência, não produtividade nem fila histórica. Inclui estimativas; filtrar qualidade exige derivar do intervalo |
| Lead time desde Entrada | `lead_time_total_min` / 60 | Exige Entrada comprovada e final comprovado se estiver terminal; desconhecidos ficam fora da média com contagem explícita |
| Cobertura histórica | Itens/visitas com evidência / universo selecionado | Exibir junto aos KPIs para não ocultar projetos sem histórico |
| Saúde da carga | Último sucesso, idade do corte, duração e métricas de `etl_run` | Diferenciar horário de referência e horário de conclusão; monitorar falhas pelo estado/log |
| Cumprimento de SLA | Visitas elegíveis com duração ≤ meta / visitas elegíveis com meta | **Pendente** de metas e implementação. Publicar quantidade sem meta e qualidade desconhecida separadamente |

Metas futuras: modelar tabela por `board_id`, `status_id`, vigência e escopo de negócio, com limite em minutos, calendário e regra por visita ou acumulado por projeto. Evitar vigências sobrepostas. Ainda definir se cada retorno recebe novo prazo, se há pausas e quais finais entram na avaliação. Aprovar essas regras antes de desenvolver a classificação.

## Proposta para o relatório de negócio

Página Projeto: pesquisa por nome/ID, status atual, corte, cobertura, linha do tempo, tabela etapa × visitas × horas observadas × horas estimadas e diagnósticos.

Página Processo: fila atual, idade observada da fila, mediana e p95 de visitas encerradas, volume da amostra e retornos. Filtros por Marca, Talento e demais atributos disponíveis, com a origem temporal informada. Atributos anteriores à primeira observação não são comprovados.

Página Qualidade e Operação: projetos sem histórico/Entrada, cadeias inconsistentes, divergência snapshot/log, última execução e atraso da carga. Dashboard/arquivo Power BI ainda não foi criado.

## Corte, atualização e produção

O código atual calcula até o início da execução. O incremental relê desde `min(último corte, início atual − RUN_WINDOW_HOURS) − OVERLAP_MINUTES`, com paginação adicional de segurança; a janela normal configurável é de 24h, mais sobreposição. IDs evitam duplicação. O snapshot dos itens é completo e os derivados do quadro são reconstruídos. Falha não avança o watermark. Atrasos maiores que a janela exigem recuperação/backfill enquanto a origem ainda disponibiliza os logs.

Fechamento D+1 à meia-noite, com execução proposta às 03h São Paulo, continua **pendente de implementação**. Agendar às 03h não produz sozinho um corte de meia-noite. Para ir ao ar antes dessa evolução, o relatório deve declarar “dados até o corte da execução”, com a hora explícita.

Pronto e validado: banco remoto preenchido, histórico disponível, pipeline executado contra a VPS, PK/FK/SK, backup com restore testado e consultas analíticas. Pendente: executor/agendamento na VPS, acesso por rede interna e papéis de acesso, rotinas de backup e monitoramento em operação, aceite da população/qualidade dos KPIs. Metas por etapa, D+1 fechado e dashboard são entregas adicionais ainda não prontas.

Não é necessário criar outro banco ou outra coluna no Monday para medir os tempos atuais. A equipe deve manter as mudanças de status na coluna configurada. Criar status novo nessa coluna é suportado; marcar um novo status como encerramento requer atualizar `FINAL_STATUS_LABELS`.

Roteiro de instalação e publicação: [DEPLOY_PASSO_A_PASSO.md](DEPLOY_PASSO_A_PASSO.md). GitHub guarda e versiona código; PostgreSQL guarda os dados; Docker executa o programa; cron determina quando rodar. Só subir o código no GitHub não agenda o pipeline.

## Tratamento e contratos de qualidade

A passagem para análise aplica limpeza textual em cópias, valida campos obrigatórios e preserva nulos legítimos. Regras de publicação, arquitetura para novas áreas e responsabilidades documentais estão em [ARQUITETURA_E_GOVERNANCA.md](ARQUITETURA_E_GOVERNANCA.md). A obrigatoriedade de cada campo está em [CONTRATOS_DE_DADOS.md](CONTRATOS_DE_DADOS.md).
