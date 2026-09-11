-- Somente leitura; não exige as tabelas removidas.
SELECT table_schema, table_name, table_type FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2;

SELECT count(*) AS passagens, count(DISTINCT item_id) AS projetos,
       count(*) - count(DISTINCT interval_id) AS duplicatas,
       min(corte_local) AS corte_min, max(corte_local) AS corte_max,
       min(cadastro_referencia_utc) AS coleta_min, max(cadastro_referencia_utc) AS coleta_max
FROM orcamento.gold_projeto_status;

-- Deve retornar zero linhas (unicidade + início/fim da sequência).
SELECT board_id,item_id FROM orcamento.gold_projeto_status GROUP BY board_id,item_id
HAVING count(*)<>max(ordem_etapa) OR min(ordem_etapa)<>1
   OR count(*)<>count(DISTINCT ordem_etapa)
   OR count(*) FILTER (WHERE intervalo_aberto)<>1
   OR count(*) FILTER (WHERE eh_primeiro_registro)<>1
   OR count(*) FILTER (WHERE eh_ultimo_registro)<>1;

-- Deve retornar zero: as CHECKs também bloqueiam novas inconsistências.
SELECT count(*) AS duracoes_divergentes FROM orcamento.gold_projeto_status
WHERE abs(duracao_horas*60-duracao_minutos)>0.00001
   OR abs(duracao_minutos-extract(epoch FROM (coalesce(saida_status_utc,corte_utc)-entrada_status_utc))/60)>0.00001;

SELECT qualidade_historico,count(*) AS passagens FROM orcamento.gold_projeto_status
GROUP BY qualidade_historico ORDER BY 1;
