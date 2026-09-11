# Estrutura do Power BI para apresentação com HTML Content

**Referência do modelo anterior:** as tabelas e medidas abaixo foram substituídas pelo consumo de [OURO_CONSUMO.md](OURO_CONSUMO.md). A preferência de apresentação por HTML Content continua; adaptar os módulos ao contrato Gold antes de usá-los.

Guia de execução no Power BI Desktop. O PBIX não foi editado nem executado pelo assistente: esta entrega contém instruções e DAX para aplicar nele. Banco e pipeline não precisam de alteração. Medidas DAX usam vírgulas e nomes importados com espaço. Layout final: HTML Content; implementação visual posterior à validação do modelo.

## 1. Preparar o arquivo

Salvar uma cópia do PBIX antes de ajustar relações. Renomear a página atual de cartões para `00 Conferência`. Manter as medidas existentes na tabela `_medidas`; não as apagar. A imagem confirma que há valores calculados, mas não comprova a fórmula de cada medida nem as colunas usadas em cada relacionamento.

Na exibição Modelo, abrir cada linha com duplo clique e conferir as colunas. Configuração proposta (todos ativos, filtro único da esquerda para a direita):

| Origem | Destino |
|---|---|
| `orcamento dim_item[item_sk]` (1) | `orcamento gold_intervals_local[item_sk]` (*) |
| `orcamento dim_status[status_sk]` (1) | `orcamento gold_intervals_local[status_sk]` (*) |
| `orcamento dim_item[item_sk]` (1) | `orcamento fct_item_sla_summary[item_sk]` (*) |
| `orcamento dim_item[item_sk]` (1) | `orcamento fct_item_status_daily[item_sk]` (*) |
| `orcamento dim_status[status_sk]` (1) | `orcamento fct_item_status_daily[status_sk]` (*) |
| `orcamento dim_item[item_id]` (1) | `orcamento data_quality_issue[item_id]` (*) |

O resumo continua tendo uma linha por item. Configurar seu lado como vários no Power BI permite filtro único e não duplica dados. A orientação anterior de `1:1 com filtro único` estava incorreta: relações 1:1 sempre são bidirecionais. [Microsoft](https://learn.microsoft.com/en-us/power-bi/guidance/relationships-one-to-one).

Manter `_medidas` e `orcamento etl_watermark` desconectadas. Não relacionar fatos entre si. Não conectar a dimensão histórica de status ao `current_status_sk` do item: são papéis diferentes. Para uma página de fila por status atual, usar futuramente uma dimensão de papel separada ou medidas específicas, sem filtrar visitas passadas pelo status atual.

## 2. Dimensões de Marca e Talento

**Atualização: aplicar agora somente a correção de Marca.** O usuário informou que talentos também aparecem em `intervenciencia`. A inspeção confirmou pessoas, apelidos, grupos, empresas e descrições nesse campo, além de múltiplos talentos no dropdown. A orientação anterior de relacionar `dim_talento` apenas a `talento` é incompleta. Siga [CORRECAO_MARCA_TALENTO.md](CORRECAO_MARCA_TALENTO.md) antes de construir filtros/rankings de talento.

Modelagem → Nova tabela, somente se a tabela ainda não existir. Se já criou `dim_marca`/`dim_talento`, cancele a janela de relacionamento, selecione a tabela calculada na exibição de dados e substitua a fórmula na barra DAX. Não criar novas medidas, colunas ou cópias das dimensões para essa correção.

A fórmula inicial preservava uma linha em branco na dimensão, causando o erro de chave do lado 1 apresentado pelo usuário. As fórmulas corrigidas removem BLANK e textos vazios/só espaços apenas dos cadastros calculados. As linhas dos fatos e seus atributos ausentes permanecem intactos.

```dax
dim_marca =
VAR Marcas =
    DISTINCT(
        UNION(
            SELECTCOLUMNS(
                'orcamento gold_intervals_local',
                "marca", 'orcamento gold_intervals_local'[marca]
            ),
            SELECTCOLUMNS(
                'orcamento fct_item_status_daily',
                "marca", 'orcamento fct_item_status_daily'[marca]
            )
        )
    )
RETURN
    FILTER(Marcas, NOT(ISBLANK([marca])) && LEN(TRIM([marca])) > 0)
```

Criar estas duas relações 1:N, filtro único:

- `dim_marca[marca]` → `orcamento gold_intervals_local[marca]`.
- `dim_marca[marca]` → `orcamento fct_item_status_daily[marca]`.

As duas relações diretas de `dim_talento` com as colunas de talento foram retiradas deste roteiro: não representam pessoas presentes nas duas fontes. Se já existem no PBIX, excluir somente essas linhas de relacionamento e suspender o uso da dimensão antiga nos filtros. Não apagar campos de origem ou medidas de duração. O modelo de talento usará identidade revisada e ponte por visita.

São dimensões do PBIX, sem criar tabelas no PostgreSQL. Não as ligar entre si ou diretamente ao cadastro/resumo. A dimensão calculada não inclui chave em branco. Os atributos ausentes continuam nos fatos; relacionamentos regulares podem representá-los pelo membro virtual `(Em branco)` nos filtros. Esse membro virtual é diferente de uma linha em branco criada pela fórmula da dimensão. Não remover projetos dos fatos nem aplicar filtro global para esconder a falta de atributos: medir cobertura no fato e excluir vazios somente do ranking. [Referência Microsoft](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand).

O teste TRIM é usado apenas para identificar textos sem conteúdo, não para transformar as chaves de um lado sem transformar o outro. A coluna categórica serve como chave deste agrupamento no BI, não como identidade corporativa de Marca/Talento entre sistemas. Variações de nome e valores com múltiplos talentos continuam como recebidos; não separar por vírgula sem validar o significado na fonte.

Ao salvar cada relação de Marca: origem = dimensão, destino = fato, coluna `marca`, cardinalidade Uma para muitos (1:*), filtro Único, Ativar marcado. Não trocar por muitos-para-muitos para contornar o erro. O resultado esperado são duas linhas de Marca ativas, com 1 na dimensão e * nos fatos. O erro mostrado se refere à chave em branco; após editar, confirmar o salvamento no PBIX antes de avançar.

Filtros dessas dimensões atingem as duas tabelas fato. **Não atingem automaticamente `dim_item`, o resumo ou qualidade.** Por isso a contagem de projetos na amostra deve vir do fato, não do cadastro. Não ativar filtros bidirecionais para tentar resolver isso.

## 3. Amostra confiável

Na tabela `orcamento gold_intervals_local`, usar Modelagem → Nova coluna. Esta coluna identifica visitas observadas, encerradas e sem os dois diagnósticos de inconsistência definidos no PRD:

```dax
Amostra Confiável =
VAR ItemId = 'orcamento gold_intervals_local'[item_id]
VAR BoardId = 'orcamento gold_intervals_local'[board_id]
VAR Problemas =
    COUNTROWS(
        FILTER(
            ALL('orcamento data_quality_issue'),
            'orcamento data_quality_issue'[item_id] = ItemId
                && 'orcamento data_quality_issue'[board_id] = BoardId
                && 'orcamento data_quality_issue'[code]
                    IN { "cadeia_status_inconsistente", "snapshot_status_divergente" }
        )
    )
RETURN
    'orcamento gold_intervals_local'[history_quality] = "observed"
        && NOT('orcamento gold_intervals_local'[is_open_interval])
        && NOT(ISBLANK('orcamento gold_intervals_local'[event_end_id]))
        && Problemas = 0
```

Ausência de Entrada não exclui todas as visitas posteriores observadas. O diagnóstico permanece visível. Atualizar o PBIX recalcula essa coluna. Atributos no fato podem ser `as_of_start`, `earliest_available` ou `unavailable`: a medição de tempo observada não garante que Marca/Talento fossem os mesmos na época. Exibir cobertura e essa ressalva nos rankings.

## 4. Corrigir nomes e preservar medidas numéricas

Renomear `Projetos em Validação` para `Projetos com Validação Encerrada`. A fórmula anterior conta projetos que passaram por validação e saíram; ela não conta os que aguardam hoje. Renomear `Projetos` para `Projetos Cadastrados` caso sua fórmula seja DISTINCTCOUNT de dim_item. Valores do print (81, 352 etc.) são de uma fotografia, não metas nem contagens permanentes.

Criar ou substituir as medidas abaixo em `_medidas`, uma de cada vez. Não incluir FORMAT nas medidas de cálculo. Usar as propriedades de formato para números; FORMAT ficará reservado à camada HTML.

```dax
Projetos na Amostra =
DISTINCTCOUNT('orcamento gold_intervals_local'[item_id])
```

```dax
Projetos com Visitas Confiáveis =
CALCULATE(
    [Projetos na Amostra],
    KEEPFILTERS('orcamento gold_intervals_local'[Amostra Confiável] = TRUE())
)
```

```dax
Mediana por Visita h =
CALCULATE(
    MEDIAN('orcamento gold_intervals_local'[duration_hours]),
    KEEPFILTERS('orcamento gold_intervals_local'[Amostra Confiável] = TRUE())
)
```

```dax
Tempo Médio por Visita h =
CALCULATE(
    AVERAGE('orcamento gold_intervals_local'[duration_hours]),
    KEEPFILTERS('orcamento gold_intervals_local'[Amostra Confiável] = TRUE())
)
```

```dax
P95 por Visita h =
CALCULATE(
    PERCENTILEX.INC(
        'orcamento gold_intervals_local',
        'orcamento gold_intervals_local'[duration_hours],
        0.95
    ),
    KEEPFILTERS('orcamento gold_intervals_local'[Amostra Confiável] = TRUE())
)
```

Medidas genéricas de validação: manter o filtro do status selecionado usando KEEPFILTERS. As três estatísticas e a contagem precisam usar a mesma amostra.

```dax
Mediana Validação h =
CALCULATE(
    [Mediana por Visita h],
    KEEPFILTERS(
        FILTER('orcamento dim_status', CONTAINSSTRING([status_label], "Validação"))
    )
)
```

```dax
Média Validação h =
CALCULATE(
    [Tempo Médio por Visita h],
    KEEPFILTERS(
        FILTER('orcamento dim_status', CONTAINSSTRING([status_label], "Validação"))
    )
)
```

```dax
P95 Validação h =
CALCULATE(
    [P95 por Visita h],
    KEEPFILTERS(
        FILTER('orcamento dim_status', CONTAINSSTRING([status_label], "Validação"))
    )
)
```

```dax
Projetos com Validação Encerrada =
CALCULATE(
    [Projetos com Visitas Confiáveis],
    KEEPFILTERS(
        FILTER('orcamento dim_status', CONTAINSSTRING([status_label], "Validação"))
    )
)
```

Não apresentar as medidas genéricas acima como prova de demora causada por Marca ou Talento. São estatísticas por visita, não mediana do tempo total por projeto. Para total de validação por projeto, somar visitas por item antes de calcular a mediana; isso é outro indicador. Cinco projetos é um limiar exploratório configurável, não garantia estatística.

Organizar pastas de exibição nas propriedades das medidas: `01 Cadastro`, `02 Permanência`, `03 Validação`, `04 Fila`, `05 Qualidade`, `90 HTML` (esta última fica vazia por enquanto). Ocultar a coluna auxiliar `_medidas` da exibição de relatório. IDs numéricos devem usar Não resumir; SKs são texto.

## 5. Definir qual demora estamos medindo

| Pergunta | Regra |
|---|---|
| Tempo das visitas com validação, agrupado por Marca | Medidas genéricas com filtro dim_marca; não atribui responsabilidade à Marca |
| Quanto aguardamos resposta da Marca? | Duas medições separadas: `Em elaboração - Retorno Marca/Executivo` e `Aguardando Feedback`, conforme confirmação do usuário |
| Tempo da etapa Validação Talento | Selecionar especificamente `Em revisão - Validação Talento` e agrupar por dim_talento |
| Tempo da etapa Talent Manager | Medir separadamente; não misturar com o tempo do Talento |
| Tempo Gestão Esporte | Medir separadamente; não tratar como resposta da Marca |

O usuário confirmou ambas as etapas da Marca, medidas separadamente, e a espera do Talento. Talent Manager continua outra etapa. Novos status devem entrar no catálogo por ID e ter sua categoria analítica revisada. Estas categorias representam a espera no processo; não provam quem causou a demora.

Criar as seis medidas abaixo depois das medidas-base do passo 4. Todas respeitam filtros existentes. Uma seleção de etapa incompatível produzirá branco; isso evita mostrar valor de outra etapa no ranking.

```dax
Mediana Retorno Marca h =
CALCULATE(
    [Mediana por Visita h],
    KEEPFILTERS(
        'orcamento dim_status'[status_label] = "Em elaboração - Retorno Marca/Executivo"
    )
)
```

```dax
Projetos Retorno Marca =
CALCULATE(
    [Projetos com Visitas Confiáveis],
    KEEPFILTERS(
        'orcamento dim_status'[status_label] = "Em elaboração - Retorno Marca/Executivo"
    )
)
```

```dax
Mediana Feedback Marca h =
CALCULATE(
    [Mediana por Visita h],
    KEEPFILTERS('orcamento dim_status'[status_label] = "Aguardando Feedback")
)
```

```dax
Projetos Feedback Marca =
CALCULATE(
    [Projetos com Visitas Confiáveis],
    KEEPFILTERS('orcamento dim_status'[status_label] = "Aguardando Feedback")
)
```

```dax
Mediana Espera Talento h =
CALCULATE(
    [Mediana por Visita h],
    KEEPFILTERS('orcamento dim_status'[status_label] = "Em revisão - Validação Talento")
)
```

```dax
Projetos Espera Talento =
CALCULATE(
    [Projetos com Visitas Confiáveis],
    KEEPFILTERS('orcamento dim_status'[status_label] = "Em revisão - Validação Talento")
)
```

Para média e P95 de cada etapa, aplicar exatamente o mesmo filtro à medida-base `Tempo Médio por Visita h` ou `P95 por Visita h`. Cada ranking usa seu próprio número de projetos para o limiar de cinco; não usar `Projetos com Validação Encerrada` para os rankings da Marca, pois essas duas etapas não contêm Validação no nome. Se os rótulos mudarem, revisar o mapeamento; não preencher resultado vazio com zero.

Uma eventual visão consolidada da Marca deverá somar os intervalos das duas etapas por projeto antes de calcular a mediana por projeto. Nunca somar as duas medianas para produzir o tempo total.

## 6. Projeto 360° e filtros

Criar uma coluna no cadastro para seleção inequívoca:

```dax
Projeto =
'orcamento dim_item'[item_name]
    & " | " & FORMAT('orcamento dim_item'[item_id], "0")
```

Esse campo identifica o projeto no futuro seletor HTML. Para mostrar o histórico completo, a página Projeto 360° recebe o projeto selecionado; filtros de etapa/período do ranking não devem ocultar silenciosamente visitas da trajetória. Testar drillthrough com esse comportamento antes de publicar. Não usar a mesma medida de amostra encerrada para o histórico completo: nele aparecem também visitas abertas e trechos estimados, com rótulos explícitos.

Definir o período antes de ligar um calendário: rankings usarão **data de saída da visita**, derivada de `status_end_local` para visitas encerradas. Permanência diária usa `fct_item_status_daily[dt]`. São perguntas diferentes. Não usar snapshot_date como data da transição. Fila atual usa o corte atual e não deve desaparecer por um filtro de período histórico. Implantar calendários por papel na etapa de filtros temporais, com escopo de cada página explícito.

## 7. Contrato de cada página HTML

| Página | Conteúdo preparado | Filtros / unidade |
|---|---|---|
| 01 Visão executiva | Projetos na amostra, mediana, P95, fila, cobertura e corte | Distinguir cadastro global de amostra filtrada; horas corridas |
| 02 Projeto 360° | Identidade, status atual, Entrada comprovada, histórico por interval_id, visitas e retornos | Um item; não inferir retrabalho apenas pelo retorno |
| 03 Marca | Dois rankings: Retorno Marca/Executivo e Aguardando Feedback; mediana, média, P95 e amostra de cada etapa | Ausência de marca separada; mínimo exploratório de 5 por etapa |
| 04 Talento | Mesmas medidas por Talento, separando Talento de Talent Manager | Nomes compostos não devem ser divididos sem regra |
| 05 Gargalos | Etapa × mediana/P95; fila × idade observada; retornos observados | Fila não é a amostra de visitas encerradas; usar definição SQL de referência |
| 06 Qualidade | Códigos, projetos distintos afetados, ausência de Entrada/atributos e corte | Contagem de códigos não é contagem de projetos; cobertura depende do contexto |

Ranking: maior mediana primeiro, empate por tamanho de amostra e nome. Esconder nomes vazios apenas do ranking. Se nenhum grupo atingir cinco projetos, mostrar estado “Amostra insuficiente”; não reduzir o mínimo silenciosamente. Média/P95/mediana são por visita. Não somar as medianas da tabela para produzir um total.

Marca/Talento no fato não filtram o cadastro/resumo de volta. Se uma página precisar que seus filtros afetem indicadores do resumo ou qualidade, criar medidas com transferência explícita dos IDs selecionados (TREATAS), ou reavaliar o modelo de atributos; testar totais. Não reutilizar os cartões globais fingindo que responderam a esses filtros.

## 8. HTML Content depois da estrutura

Usar módulos separados para KPIs, rankings e trajetória. A medida numérica calcula; uma medida HTML apenas apresenta. No ranking interativo, passar `dim_marca[marca]` ou `dim_talento[talento]` em **Granularity**, a medida de apresentação em **Values**, e medidas de apoio em Tooltips. Isso cria o contexto de linhas necessário para seleção e cross-filtering. Uma página inteira em uma única string não oferece essa seleção automaticamente. [Documentação do HTML Content](https://html-content.com/docs/interactivity).

Testar a versão/edição instalada antes de prometer seletores de busca, menus e navegação de páginas. Elementos HTML arbitrários não substituem automaticamente ações do Power BI. Validar clique → filtro → detalhes por projeto no componente real. Escapar valores vindos dos dados ao compor HTML; não incorporar JSON bruto ou HTML da fonte. Não criar HTML ou comprar componentes nesta etapa.

## 9. Validação antes do layout

1. Conferir cada coluna de relacionamento e garantir ausência de ligações extras entre fatos.
2. Em Modelagem/consulta DAX, ou na página técnica existente, comparar as mesmas medidas por Marca/Talento. A tabela de conferência, se usada, não é layout de produção.
3. Confirmar que uma Marca filtra a contagem no fato, mediana e amostra; o cadastro global continuará global por definição.
4. Conferir que mediana/média/P95 e número de projetos usam a mesma amostra, etapa e período.
5. Abrir um item pelo ID, mostrar cada interval_id e comparar as horas com a consulta 2 de `sql/006_analise_projeto.sql`.
6. Conferir retornos e a distinção entre horas observadas/estimadas. Data de saída de visita aberta é corte, não evento.
7. Testar zero resultados, um projeto, nome duplicado, grupo com menos de cinco projetos e atributo vazio.
8. O valor “5 Mil” do cartão é arredondamento de apresentação, não evidência de erro no banco. Durante conferência, usar unidade de exibição Nenhuma e número inteiro.

Este guia substitui a orientação anterior de montar seis páginas de visuais nativos. Até executar o DAX no PBIX, as fórmulas são propostas revisadas, não testes de execução concluídos. O código do pipeline e os dados não foram alterados para esse roteiro.
