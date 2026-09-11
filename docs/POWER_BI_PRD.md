> **Aplicação 3.0:** o banco tem fisicamente apenas `orcamento.gold_projeto_status`. Consultas/relacionamentos antigos devem ser retirados do PBIX. Quarentena é relatório privado CSV fora do banco; detalhes no guia de revisão.

# Power BI — modelo atual de consumo

Versão 2.2.0. O modelo antigo de sete tabelas foi substituído. A tabela de indicadores é **`orcamento.gold_projeto_status`**. O guia completo dos campos está em [OURO_CONSUMO.md](OURO_CONSUMO.md); as regras e o corte em [PRD_ELT_REGRAS.md](PRD_ELT_REGRAS.md).

## Passo a passo

1. Salvar uma cópia do PBIX atual antes de substituir consultas.
2. Obter Dados → PostgreSQL → conexão existente → **Importar** → marcar somente `orcamento.gold_projeto_status`.
3. No novo modelo, remover/desabilitar a carga das consultas antigas e das dimensões de Marca/Talento feitas no Power Query. Não combinar as passagens antigas e novas.
4. O nome normalmente fica **`orcamento gold_projeto_status`**, com espaço. DAX neste projeto usa **vírgula** como separador de argumentos.
5. Datas locais: Data/Hora. Durações: Número decimal. Retorno/primeira/última linha: Verdadeiro/Falso. IDs, SKs e ordem: Não resumir.
6. Criar as medidas de [power_bi_gold.dax](../powerbi/power_bi_gold.dax), uma por vez. Elas agregam a tabela pronta; limpeza de nomes, corte, exclusão e cálculo de permanência já são feitos em Python.
7. Usar os campos da própria Gold para filtros. Não há relacionamento obrigatório para esse modelo de uma tabela.
8. Atualizar após o término da carga e exibir `corte_local`. A carga começa às 06h, mas a disponibilidade depende de quando termina. O corte fecha o dia anterior; não é a hora da atualização do PBIX.

## Projeto 360° — primeira página a montar

Filtrar por `item_id` e `projeto_nome`, com um projeto selecionado. Mostrar:

- Etapa: `status_nome`.
- Entrada/saída: `entrada_status_local`, `saida_status_local`.
- Horas: `duracao_horas`.
- Retorno: `eh_retorno`.
- Qualidade: `qualidade_historico`.
- Marca, Talento e responsável: `marca_nome`, `talento_nome`, `responsavel_orcamento`.
- Ordenação: `ordem_etapa`, crescente.

Cards podem exibir status no corte, tempo desde Entrada comprovada, tempo na última etapa, número de etapas, passagens e retornos. A saída da última linha é nula. Total desconhecido não deve aparecer como zero. A primeira linha é o primeiro trecho disponível, não necessariamente uma Entrada comprovada.

## Indicadores e comparações

| Indicador | Cálculo/grão correto |
|---|---|
| Projetos elegíveis | DISTINCTCOUNT de `item_sk` |
| Passagens | COUNTROWS da Gold |
| Horas por status | SUM de `duracao_horas`, com qualidade explícita |
| Mediana/P95 de permanência | Passagens com `elegivel_comparacao=true` |
| Projetos na fila no corte | Projetos distintos com `projeto_na_fila=true`; atividade cadastral observada na coleta |
| Retornos | Contar passagens com `eh_retorno=true` |
| Tempo desde Entrada | MAX por projeto; nunca somar o valor repetido nas passagens |
| Último corte | MAX de `corte_local` |

Comparar Marca e Talento pela mediana por passagem observada encerrada, com média/P95 e quantidade de projetos distintos da amostra. Excluir nomes vazios e considerar um mínimo de cinco projetos como critério de exibição, não regra que apaga dados. O número da amostra deve usar o mesmo filtro de status e qualidade do tempo.

Separar as três esperas: **Em elaboração - Retorno Marca/Executivo**, **Aguardando Feedback** e **Em revisão - Validação Talento**. Não somar medianas para formar tempo combinado; se desejar total por projeto nas duas etapas de Marca, primeiro somar as passagens por projeto e depois calcular a mediana desses totais.

Filtros de período precisam ter significado: entrada na etapa, saída ou corte de publicação. Não usar a data do corte para simular série de snapshots antigos: a Gold guarda a trajetória recalculada no último fechamento, não uma cópia imutável de cada publicação.

## Páginas previstas

1. Visão executiva: volume elegível, fila, mediana/P95 por etapa, retorno e corte.
2. Projeto 360°: trajetória individual completa disponível.
3. Marca: esperas separadas, ranking e tamanho de amostra.
4. Talento: espera de validação e projetos que compõem o resultado.
5. Gargalos e retornos: status × tempo, retorno × tempo total por projeto, volume × mediana.
6. Saneamento: acompanhar o CSV privado `projetos_quarentena.csv` exportado pelo executor. Não existe tabela adicional de saneamento no PostgreSQL.

A quarentena não compõe KPIs de projetos elegíveis e não deve ser unida às passagens. Não misturar contagens da fila de saneamento com o volume da Gold sem considerar o corte. Guia: [QUARENTENA_E_IDENTIDADES.md](QUARENTENA_E_IDENTIDADES.md).

O layout final será feito com HTML Content conforme solicitado. Esta etapa entrega a base e as medidas; nenhum PBIX ou visual HTML foi editado automaticamente. Filtros/interações devem respeitar as capacidades reais do visual escolhido.

Associação entre Marca/Talento e demora não prova responsabilidade causal. Os responsáveis são do cadastro observado, não histórico comprovado de cada passagem. Não existem metas aprovadas para classificar dentro/fora do SLA.
