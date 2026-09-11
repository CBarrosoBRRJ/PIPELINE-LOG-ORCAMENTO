-- Inventário: exatamente as duas tabelas autorizadas no schema orcamento.
SELECT table_name FROM information_schema.tables WHERE table_schema='orcamento' ORDER BY 1;
-- Volumes e duplicidade física/negocial (as constraints também bloqueiam duplicatas).
SELECT count(*) AS passagens, count(DISTINCT item_id) AS projetos,
       count(*)-count(DISTINCT interval_id) AS ids_duplicados,
       count(*)-count(DISTINCT (board_id,item_id,ordem_etapa)) AS ordens_duplicadas
FROM orcamento.gold_projeto_status;
SELECT qualidade_historico, count(*) AS registros, count(duracao_horas) AS tempos_comprovados
FROM orcamento.gold_projeto_status GROUP BY 1 ORDER BY 1;
SELECT excluido_da_analise, count(*) AS projetos FROM orcamento.pendencias_projeto GROUP BY 1;
-- Deve retornar zero: um projeto excluído nunca entra na Gold.
SELECT count(*) AS exclusoes_inconsistentes FROM orcamento.pendencias_projeto p
WHERE p.excluido_da_analise AND EXISTS(SELECT 1 FROM orcamento.gold_projeto_status g
 WHERE g.board_id=p.board_id AND g.item_id=p.item_id);
