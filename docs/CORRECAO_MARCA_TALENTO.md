# Correção de Marca e revisão da identidade de Talento

**Referência histórica, substituída pela versão 2:** usar [OURO_CONSUMO.md](OURO_CONSUMO.md). Não executar este tratamento manual/expansão no novo PBIX; as regras agora ficam no pipeline.

Este roteiro corrige as instruções anteriores. DAX usa vírgulas e tabelas com espaço depois de `orcamento`. É uma orientação para o PBIX; não foi aplicada ao arquivo do usuário nem altera a base PostgreSQL.

## 1. O erro de relacionamento

A imagem mostra uma linha null em `dim_marca[marca]`, no lado 1. A fórmula anterior com DISTINCT/UNION conservava esse valor, rejeitado ao salvar a relação. Não mudar para muitos-para-muitos. Não excluir os projetos sem marca do fato e não converter NULL em texto literal "null".

1. Cancelar a janela de relacionamento.
2. Selecionar a tabela calculada `dim_marca`, na exibição de dados/tabela.
3. Exibir a barra de fórmulas se estiver oculta.
4. Substituir a fórmula inteira da tabela pela expressão abaixo. Não criar uma medida nem outra cópia de dim_marca.

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

5. Confirmar a fórmula e salvar as relações:

| Origem (1) | Destino (*) | Filtro |
|---|---|---|
| `dim_marca[marca]` | `orcamento gold_intervals_local[marca]` | Único |
| `dim_marca[marca]` | `orcamento fct_item_status_daily[marca]` | Único |

Ativar ambas. Não marcar integridade referencial presumida. A imagem já mostra as colunas, a cardinalidade e a direção corretas; o problema é o conteúdo em branco da dimensão. O filtro só retira branco do cadastro. Valores ausentes continuam nos fatos e podem aparecer como membro virtual em branco ao consumir a relação regular. Textos como "null" ou "N/A" não devem ser eliminados por suposição.

## 2. O problema adicional de Talento

Fonte confirmada no catálogo real:

| Origem Monday | ID | Tipo | Coluna analítica |
|---|---|---|---|
| Talentos Exclusivos | `dropdown_mkvdz0zv` | dropdown | `talento` |
| Interveniência | `text_mkvcwrrb` | text | `intervenciencia` |

Na consulta desta revisão: 5.355 visitas, 3.312 com talento não nulo, 1.876 com interveniência não nula e 16 com ambas. São contagens de visitas, não pessoas/projetos, e podem mudar na próxima atualização. A coluna texto contém pessoas, abreviações, grupos, empresas e descrições de ação. O dropdown também contém registros com múltiplas seleções.

A informação adicional do usuário define que pessoas das duas fontes devem entrar na análise. Não define que qualquer texto de Interveniência seja uma pessoa, nem que dois nomes parecidos identifiquem a mesma pessoa.

Por isso:

- Não usar COALESCE(talento, intervenciencia): descartaria a segunda fonte quando ambas existem.
- Não concatenar os nomes e tratar a combinação como uma única pessoa.
- Não conectar uma dimensão única às duas colunas para tentar representar uma condição OU; relações simultâneas não implementam essa lógica.
- Não dividir livremente por vírgula, barra ou sinal de mais; recuperar as seleções estruturadas do dropdown pela Bronze e revisar as listas no texto livre.
- Não assumir que apelidos e nomes parecidos são a mesma identidade sem correspondência validada.

As duas colunas já estão nos dados do pipeline. Não é necessário refazer o backfill para começar essa revisão.

## 3. O que fazer agora no Power BI

1. Corrigir Marca e salvar seus dois relacionamentos.
2. Se foram criadas relações diretas `dim_talento[talento]` → fatos[talento], remover somente essas linhas. Manter os dados e medidas; não usar o ranking anterior como ranking completo de talentos.
3. Em Transformar dados (Power Query), clicar com o botão direito na consulta `orcamento gold_intervals_local` e escolher **Referência**.
4. Nomear a consulta `auditoria_talento_origem`.
5. Manter apenas `interval_id`, `item_id`, `board_id`, `snapshot_date`, `attribute_source`, `talento` e `intervenciencia`.
6. Selecionar somente as duas últimas colunas e escolher **Transformar colunas em linhas** (Unpivot Columns).
7. Renomear Atributo para `origem_coluna` e Valor para `valor_original`.
8. Filtrar valores nulos, vazios ou compostos apenas por espaços apenas nesta consulta de auditoria. Não aplicar esse filtro à consulta original de intervalos.
9. Não mesclar a auditoria de volta ao fato para somar horas; uma visita pode aparecer mais de uma vez nela. Ela serve para revisar origem e identificar quem foi mencionado.
10. Para uma lista compacta de revisão, criar uma referência dessa auditoria, manter `origem_coluna` e `valor_original` e remover duplicatas nesse par. Não apagar duplicatas do fato nem usar nomes para identificar os projetos.

As consultas de auditoria podem ficar com carregamento desabilitado durante a revisão; não criar relacionamentos automáticos com elas. Não introduzir um dashboard nativo: esse trabalho prepara o modelo para HTML Content.

## 4. Modelo definitivo de talentos

Decisão posterior confirmada: o ranking deve incluir **somente pessoas individuais**. Duplas e perfis coletivos (incluindo os exemplos Bruno e Marrone, Manual do Mundo e PodPah) ficam fora do ranking individual, preservados e classificados. Não expandir coletivos automaticamente. A lista enviada de Interveniência tem 810 textos distintos e 13 grupos candidatos de variação apenas por acento/caixa; a proposta privada de revisão está em `runtime/REVISAO_TALENTOS_INTERVENIENCIA.md`. Candidatos de identidade não foram aplicados ao banco/PBIX.

Depois da revisão de identidades, a estrutura analítica deve separar:

| Objeto | Grão / regra |
|---|---|
| Catálogo de correspondências | Fonte + valor original + pessoa extraída → ID de talento canônico, nome de exibição, classificação e revisão |
| Dimensão de talentos | Uma linha por pessoa confirmada, com chave estável não nula |
| Evidência de atribuição | Uma linha por visita + talento + origem; conserva ambas as colunas quando ambas citam a pessoa |
| Ponte de consumo | Uma linha por interval_id + talento_id, sem horas repetidas; deduplicar o mesmo talento presente nas duas fontes |

Classificações: pessoa, grupo, empresa/outro e pendente. Grupo não é uma pessoa e não pode ser expandido sem conhecer seus integrantes. Ausência de talento segue ausência; pendentes aparecem na cobertura da revisão, não em ranking de pessoas confirmadas. Guardar os valores originais e a decisão de correspondência para manutenção.

A dimensão filtra a ponte (1:N, único). Para aplicar a seleção ao fato, uma medida transfere os interval_id distintos da ponte ao fato com TREATAS e KEEPFILTERS. Não habilitar bidirecionalidade global. [Microsoft: TREATAS](https://learn.microsoft.com/en-us/dax/treatas-function-dax).

Requisitos de validação: a mesma pessoa citada nas duas fontes conta uma visita; dois talentos associados à mesma visita podem aparecer em seus rankings individuais, mas o total geral deve contar a visita uma única vez. Associação à visita não mede tempo de resposta individual se dois talentos aguardaram juntos. Não dividir ou atribuir horas como responsabilidade individual sem eventos próprios.

A ponte deve usar os atributos da visita, respeitando `attribute_source`. Não usar apenas o talento atual de dim_item para atribuir todo o passado. A tabela diária precisa de atribuição no seu próprio grão; a ponte de intervalos não deve ser conectada à diária por item_id. Sua extensão fica para depois da validação do ranking por visitas.

## 5. Critérios antes de publicar o ranking

Conferir: talento só em Exclusivos; só em Interveniência; duas pessoas nas duas colunas; mesma pessoa nas duas colunas; múltiplos exclusivos; texto com empresas/grupos; nome abreviado sem correspondência; seleção de vários talentos sem duplicar o total. Não considerar que o novo modelo já foi executado no PBIX: a revisão e implementação da ponte estão pendentes.

Marca continua separada em Retorno Marca/Executivo e Aguardando Feedback. Talento mede a etapa Validação Talento; Talent Manager continua uma etapa independente. Layout final permanece HTML Content após a validação dos cálculos.
