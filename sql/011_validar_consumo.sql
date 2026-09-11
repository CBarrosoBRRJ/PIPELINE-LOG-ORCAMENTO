-- Somente leitura. Execuções e cortes são relógios distintos.
SELECT count(*) AS passagens, count(DISTINCT item_sk) AS projetos,
       count(*) - count(DISTINCT interval_id) AS ids_duplicados,
       min(corte_local) AS corte_minimo, max(corte_local) AS corte_maximo,
       min(versao_regras) AS versao_minima, max(versao_regras) AS versao_maxima
FROM orcamento.gold_projeto_status;

-- Deve retornar zero linhas.
SELECT board_id,item_id,ordem_etapa,count(*)
FROM orcamento.gold_projeto_status GROUP BY 1,2,3 HAVING count(*)>1;

-- Deve retornar zero linhas.
SELECT item_id FROM orcamento.gold_projeto_status GROUP BY item_id
HAVING count(*) FILTER(WHERE eh_primeiro_registro)<>1
    OR count(*) FILTER(WHERE eh_ultimo_registro)<>1
    OR count(*) FILTER(WHERE intervalo_aberto)<>1;

-- Deve ser zero.
SELECT count(*) AS projetos_excluidos_presentes
FROM orcamento.gold_projeto_status g
JOIN orcamento.data_quality_issue q USING(board_id,item_id)
WHERE q.code='gold_projeto_excluido';

-- Deve ser zero: reconciliação de duração em horas com datas/corte.
SELECT count(*) AS duracoes_invalidas FROM orcamento.gold_projeto_status
WHERE entrada_status_utc>=corte_utc
   OR abs(duracao_horas - extract(epoch FROM
      (coalesce(saida_status_utc,corte_utc)-entrada_status_utc))/3600)>0.000001;

SELECT start_at,end_at,mode,status,metrics->>'scheduled_date' AS data_agendada,
       metrics->>'gold_cut_utc' AS corte_gold,metrics->>'gold_rules_version' AS regras
FROM orcamento.etl_run ORDER BY start_at DESC LIMIT 10;

-- Os resultados representam passagens: para contar projetos, filtrar última linha.
SELECT talento_situacao,count(*) AS projetos FROM orcamento.gold_projeto_status
WHERE eh_ultimo_registro GROUP BY talento_situacao ORDER BY projetos DESC;

SELECT code,count(*) AS projetos FROM orcamento.data_quality_issue
GROUP BY code ORDER BY projetos DESC;

SELECT motivo,count(*) AS projetos
FROM orcamento.quarentena_projeto q
CROSS JOIN LATERAL jsonb_array_elements_text(q.motivos) AS motivo
GROUP BY motivo ORDER BY projetos DESC;

-- Deve ser zero. Não comparar nomes para reconciliar populações.
SELECT count(*) AS projetos_nas_duas_saidas
FROM orcamento.quarentena_projeto q
JOIN orcamento.gold_projeto_status g USING(board_id,item_id);
