-- PostgreSQL 3.0: só a tabela final. Execute uma consulta por vez.
-- 1. Localizar o projeto e copiar item_id.
SELECT DISTINCT item_id, projeto_nome
FROM orcamento.gold_projeto_status
WHERE projeto_nome ILIKE '%parte do nome%'
ORDER BY projeto_nome;

-- 2. Substituir 123 pelo ID Monday real.
SELECT ordem_etapa AS ordem, item_id, projeto_nome AS projeto, status_nome AS status,
       entrada_status_local AS entrada, saida_status_local AS saida,
       duracao_horas, marca_nome AS marca, talento_nome AS talento,
       responsavel_orcamento, eh_retorno AS retorno, intervalo_aberto,
       qualidade_historico, corte_local
FROM orcamento.gold_projeto_status
WHERE item_id = 123
ORDER BY ordem_etapa;

-- 3. Tempo por status do projeto, incluindo retornos.
SELECT status_nome, count(*) AS passagens, sum(duracao_horas) AS horas,
       bool_or(eh_retorno) AS teve_retorno
FROM orcamento.gold_projeto_status WHERE item_id = 123
GROUP BY status_nome ORDER BY horas DESC;
