# Power BI — consumo 3.1.0

## Carregar

1. Salve uma cópia do PBIX. Em Obter Dados → PostgreSQL, use a conexão `dados_globo`, modo **Importar**.
2. Selecione `orcamento.gold_projeto_status` e `orcamento.pendencias_projeto`. Desabilite/remova as consultas antigas de dimensões/fatos para não misturar versões.
3. Se já carregou a Gold antiga, atualize a prévia no Power Query e remova etapas que mencionem colunas retiradas (JSONs, marcadores técnicos). A Gold atual tem os dez campos do exemplo primeiro, IDs e controles depois.
4. O Power BI costuma nomear com espaço: `'orcamento gold_projeto_status'`. Medidas DAX usam **vírgula**, não ponto e vírgula. Exemplos: [power_bi_gold.dax](../powerbi/power_bi_gold.dax).
5. Datas locais: Data/Hora. Horas: Número decimal. `ordem_etapa`: Número inteiro e Não resumir. `item_id`: Número inteiro de 64 bits e Não resumir (pode exibir como texto no visual). SKs/IDs compostos: Texto. `eh_retorno`, `intervalo_aberto`, `status_final`: Booleano.

## Projeto 360° — montar primeiro

Filtre por `item_id`/`projeto_nome`. Monte a tabela (ou posteriormente HTML Content) com:

| Título | Campo da Gold |
|---|---|
| Ordem | ordem_etapa |
| Projeto | projeto_nome |
| Status | status_nome |
| Entrada | entrada_status_local |
| Saída | saida_status_local |
| Duração (h) | duracao_horas |
| Marca | marca_nome |
| Talento | talento_nome |
| Responsável Orçamento | responsavel_orcamento |
| Retorno | eh_retorno |

Ordene **Ordem crescente**, com um projeto selecionado. Não ordenar alfabeticamente pelo Status nem pela ordem das etiquetas no Monday. Retornos mantêm o mesmo status, mas recebem nova ordem. Inclua ID e qualidade em tooltip/detalhe.

Entrada/duração vazias significam **não comprovadas**, não zero. Para saída vazia: se status_final=false, mostrar “Sem saída até o corte”; se true, “Último status — final”. Não chamar todo intervalo aberto de projeto em andamento.

Exemplo real: ID **12999866197**, `[Serasa] Beatriz Reis`, possui Entrada, elaboração, validações e retornos. Um trecho Sem status anterior à Entrada tem início não comprovado; a linha é preservada e sinalizada. A consulta [006_analise_projeto.sql](../sql/006_analise_projeto.sql) apresenta a sequência real.

## Indicadores

- Projetos: DISTINCTCOUNT(item_sk), não COUNTROWS.
- Registros de status: COUNTROWS. Passagens comprovadas: filtrar qualidade_historico=observed.
- Mediana/média/P95: `horas_observadas_encerradas` ou `elegivel_comparacao=true`; não misturar etapas abertas com concluídas.
- Horas por etapa: duracao_horas contém apenas tempos com início comprovado; o último trecho conta até o corte. Ausência não vira zero.
- Tempo desde Entrada e tempo no status atual: MAX por projeto, pois o valor se repete nas linhas. Não somar totais repetidos.
- Retornos: linhas eh_retorno=true. Fila: projetos distintos com projeto_na_fila=true.
- Atualização dos tempos: MAX(corte_local). Cadastro: cadastro_referencia_utc.

Marca: separar “Em elaboração - Retorno Marca/Executivo” e “Aguardando Feedback”. Talento: “Em revisão - Validação Talento”. Ranking pela mediana, com tamanho da amostra; mínimo sugerido de cinco projetos com trechos elegíveis. Não somar medianas para combinar etapas: somar por projeto e depois calcular a mediana entre projetos.

## Página de pendências

Use **pendencias_projeto**, uma linha por projeto: item_id, projeto_nome, excluido_da_analise, motivos, como_corrigir e os valores originais. Filtre primeiro excluido_da_analise=true para revisar os projetos fora da principal. Os demais são avisos de dados incompletos; podem continuar em análises de volume, com tempos desconhecidos em branco.

Não fazer Append/união com a Gold: os grãos são diferentes. As duas páginas podem funcionar sem relacionamento. Se precisar cruzar um projeto, use item_sk (uma linha de pendências para várias passagens), direção única pendências → Gold; isso filtra apenas os projetos com pendências. Não usar a tabela de pendências como cadastro completo de todos os projetos, pois os sem pendências não estão nela. Futuras bases devem usar ID da mesma origem e declarar cardinalidade.

Corrigir no Monday e atualizar o Power BI após a próxima carga concluir. Pendências resolvidas desaparecem automaticamente. Não editar o PostgreSQL para tentar corrigir a origem. Limitações históricas podem exigir exportação anterior e não se resolvem inventando transições.

Páginas seguintes: visão executiva, validação por Marca, por Talento e gargalos/retornos. Layout HTML Content será uma etapa posterior; os campos e as medidas permanecem os mesmos. Nenhum PBIX/HTML foi alterado automaticamente aqui.
