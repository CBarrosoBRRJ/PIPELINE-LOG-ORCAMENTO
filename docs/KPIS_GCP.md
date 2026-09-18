# Perguntas e métricas da tabela sla_orcamento

Pergunta central: **quanto tempo cada projeto permaneceu em cada status?**
O Python já resolve joins, nomes, sequenciamento, exclusões, qualidade, retornos e calendário. BI só seleciona, filtra e agrega a tabela pronta.

| Pergunta | Campo/agregação | População e limite |
|---|---|---|
| Quanto durou esta passagem? | duracao_horas_uteis; comparar duracao_horas | Inclui aberta até corte quando início é observado; desconhecido NULL |
| Quanto o projeto acumulou neste status, incluindo retornos? | SUM(duracao_horas_uteis) por item_id/status_id | NULLs não significam zero; apresentar contagem de passagens sem duração |
| Qual a duração típica de uma passagem encerrada? | média/mediana/percentil de horas_uteis_observadas_encerradas | Apenas elegivel_comparacao=true; denominador é número de passagens válidas, não projetos |
| Quanto o projeto levou desde Entrada? | MAX(tempo_desde_entrada_horas_uteis) por item_id | Exige Entrada comprovada; nunca somar valores repetidos entre passagens |
| Há quanto tempo está no status atual? | MAX(tempo_status_atual_horas_uteis) por item_id | Começo comprovado; status terminal aberto não significa projeto em andamento |
| Quantas voltas ao mesmo status? | COUNTIF(eh_retorno) | Retorno é uma passagem legítima; interval_id distinto |
| Quantos projetos estão em fila? | COUNT(DISTINCT item_id) WHERE projeto_na_fila | Um projeto aparece em várias linhas; não contar linhas |
| Até quando os números estão fechados? | MAX(corte_local) | Fechamento D+1; atributos têm timestamp de coleta separado |

Não existe meta ou classificação atrasado/no prazo. Tempos úteis medem exposição ao expediente acordado, não horas de esforço da pessoa. Feriados locais não cadastrados não são descontados. Para comparações por período, documentar se filtro usa data de entrada ou saída; filtrar entrada corta passagens antigas ainda abertas. Tabela não é fotografia histórica da fila de todos os dias.

No Power BI use conector Google BigQuery e selecione somente sla_orcamento, com credencial de leitura corporativa. Renomeie a consulta para sla_orcamento. Não recriar joins de dimensões PostgreSQL. Medidas opcionais estão em powerbi/power_bi_gold.dax; sua execução em Power BI ainda precisa ser validada no ambiente do consumidor.

## Precisão das horas publicadas

Todos os campos numéricos de horas em `sla_orcamento` são arredondados em Python a no máximo três casas decimais na projeção final (round, empate para o par). Cálculos, evidências e estado interno preservam precisão completa; desconhecidos continuam NULL. Origem, grão, chaves e tipos FLOAT64 permanecem iguais. BI recebe valores já arredondados; somas podem apresentar pequenas diferenças de arredondamento. A validação ocorre antes e depois da projeção; falha bloqueia a publicação.
