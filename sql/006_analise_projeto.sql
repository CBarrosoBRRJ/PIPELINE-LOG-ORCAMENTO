-- Projeto real: [Serasa] Beatriz Reis. Troque o item_id para consultar outro.
-- Os nomes abaixo são de apresentação; nenhuma tabela/view adicional é criada.
SELECT ordem_etapa AS "Ordem", projeto_nome AS "Projeto", status_nome AS "Status",
       entrada_status_local AS "Entrada", saida_status_local AS "Saída",
       round(duracao_horas::numeric, 2) AS "Duração (h)",
       marca_nome AS "Marca", talento_nome AS "Talento",
       responsavel_orcamento AS "Responsável Orçamento", eh_retorno AS "Retorno",
       item_id AS "ID Projeto", qualidade_historico AS "Qualidade", corte_local AS "Corte"
FROM orcamento.gold_projeto_status
WHERE item_id = 12999866197
ORDER BY item_id, ordem_etapa;

-- Localizar outro projeto pelo nome (execute esta consulta separadamente).
SELECT DISTINCT item_id, projeto_nome
FROM orcamento.gold_projeto_status
WHERE projeto_nome ILIKE '%Lolla%'
ORDER BY projeto_nome, item_id;

-- Fluxo do projeto mostrado na captura enviada pelo usuário.
SELECT * FROM orcamento.gold_projeto_status
WHERE item_id = 12969876209
ORDER BY item_id, ordem_etapa;

-- Lista para revisão, separada das passagens.
SELECT * FROM orcamento.pendencias_projeto
ORDER BY excluido_da_analise DESC, projeto_nome, item_id;
