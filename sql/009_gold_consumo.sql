-- Somente leitura. Substitua o ID do exemplo pelo ID real do projeto.
SELECT item_id, projeto_nome, ordem_etapa, status_nome,
       entrada_status_local, saida_status_local, duracao_horas,
       marca_nome, talento_nome, responsavel_orcamento, eh_retorno,
       qualidade_historico, intervalo_aberto, corte_local
FROM orcamento.gold_projeto_status
WHERE item_id = 123
ORDER BY ordem_etapa;

-- Totais por projeto e etapa: retornos somam tempo, sem perder detalhe na fonte.
SELECT item_id, projeto_nome, status_id, status_nome,
       COUNT(*) AS passagens, SUM(duracao_horas) AS horas,
       COUNT(*) FILTER (WHERE eh_retorno) AS retornos
FROM orcamento.gold_projeto_status
GROUP BY item_id, projeto_nome, status_id, status_nome;

-- Amostra observada encerrada, sem mistura de estimativas e fila aberta.
SELECT status_nome, COUNT(DISTINCT item_sk) AS projetos_amostra,
       COUNT(*) AS passagens,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY duracao_horas) AS mediana_h,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY duracao_horas) AS p95_h
FROM orcamento.gold_projeto_status
WHERE elegivel_comparacao
GROUP BY status_nome;

-- Auditoria de exclusão: cada projeto pode ter vários motivos.
SELECT detail::jsonb->'motivos' AS motivos, COUNT(*) AS projetos
FROM orcamento.data_quality_issue
WHERE code = 'gold_projeto_excluido'
GROUP BY 1;

SELECT entity_type, review_status, COUNT(*) AS grafias
FROM orcamento.meta_entity_mapping GROUP BY 1,2;

-- Conferência da versão do executor no banco: campos Gold presentes no etl_run
-- indicam execução pelo código novo, diferente de um replay manual da Gold.
SELECT start_at, end_at, status,
       metrics->>'gold_rules_version' AS versao_gold,
       metrics->>'gold_projects' AS projetos_gold
FROM orcamento.etl_run ORDER BY start_at DESC LIMIT 5;
