-- Read-only queries. Default destination confirmed by the user.
SELECT
  COUNT(*) AS passagens,
  COUNT(DISTINCT interval_id) AS chaves_distintas,
  COUNT(DISTINCT item_id) AS projetos,
  MAX(corte_local) AS ultimo_corte,
  COUNTIF(duracao_horas_uteis IS NULL) AS duracoes_desconhecidas,
  COUNTIF(duracao_horas_uteis > duracao_horas + 0.000001) AS horas_invalidas,
  COUNTIF(qualidade_historico != 'observed' AND
    (duracao_horas_uteis IS NOT NULL OR entrada_status_utc IS NOT NULL)) AS inferencias_expostas
FROM `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento`;

-- A passagem: no join or calendar calculation required in SQL/BI.
SELECT item_id, projeto_nome, ordem_etapa, status_nome,
  entrada_status_local, saida_status_local,
  duracao_horas_uteis, duracao_horas, eh_retorno, qualidade_historico
FROM `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento`
ORDER BY item_id, ordem_etapa;

-- Accumulated time by project/status; report unknowns instead of treating them as zero.
SELECT item_id, projeto_nome, status_id, status_nome,
  COUNT(*) AS passagens,
  SUM(duracao_horas_uteis) AS horas_uteis_conhecidas,
  COUNTIF(duracao_horas_uteis IS NULL) AS passagens_sem_duracao
FROM `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento`
GROUP BY item_id, projeto_nome, status_id, status_nome;
