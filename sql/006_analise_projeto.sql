-- Consultas somente leitura para DBeaver / PostgreSQL da VPS.
-- Execute UMA consulta por vez. O DBeaver solicita os parâmetros :termo e :item_id.
-- Informe item_id sem pontos/separadores. board_id fixa o escopo atual.
-- Em outro ambiente, substitua rede_globo pelo PG_SCHEMA correspondente.

-- 1. Localizar o projeto pelo nome e obter o ID original do Monday.
SELECT i.item_id, i.item_name, s.status_label AS status_atual, i.is_active,
       i.last_seen_at AT TIME ZONE 'America/Sao_Paulo' AS ultima_observacao
FROM rede_globo.dim_item i
JOIN rede_globo.dim_status s ON s.status_id = i.current_status_id
WHERE i.board_id = 18429499488 AND i.item_name ILIKE '%' || :termo || '%'
ORDER BY i.item_name, i.item_id LIMIT 100;

-- 2. Linha do tempo: cada visita a uma etapa, incluindo retornos.
-- fim_ou_corte é o corte de cálculo se ainda_aberto=true, não uma saída real.
SELECT f.item_id, i.item_name, f.status_id, f.status_to AS etapa,
       f.status_start_utc AT TIME ZONE 'America/Sao_Paulo' AS inicio,
       f.status_end_utc AT TIME ZONE 'America/Sao_Paulo' AS fim_ou_corte,
       round(CAST(f.duration_hours AS numeric), 2) AS horas,
       f.is_open_interval AS ainda_aberto, f.history_quality AS qualidade,
       f.event_start_id, f.event_end_id, f.interval_id
FROM rede_globo.fct_item_status_interval f
JOIN rede_globo.dim_item i USING (item_id, board_id)
WHERE f.board_id = 18429499488 AND f.item_id = :item_id
ORDER BY f.status_start_utc, f.status_end_utc, f.interval_id;

-- 3. Tempo acumulado por status do projeto. Se voltou à etapa, soma as visitas.
-- Observado/estimado são separados. Diagnósticos da consulta 5 continuam relevantes.
SELECT f.item_id, s.status_label AS etapa, count(*) AS visitas,
       count(*) FILTER (WHERE f.history_quality = 'observed') AS visitas_observadas,
       count(*) FILTER (WHERE f.history_quality <> 'observed') AS trechos_estimados,
       round(CAST(sum(f.duration_hours) AS numeric), 2) AS horas_totais,
       round(CAST(coalesce(sum(f.duration_hours) FILTER
           (WHERE f.history_quality = 'observed'), 0) AS numeric), 2) AS horas_observadas,
       round(CAST(coalesce(sum(f.duration_hours) FILTER
           (WHERE f.history_quality <> 'observed'), 0) AS numeric), 2) AS horas_estimadas,
       bool_or(f.is_open_interval) AS contem_intervalo_aberto,
       max(f.updated_at) AS corte_utc
FROM rede_globo.fct_item_status_interval f
JOIN rede_globo.dim_status s USING (status_id, board_id)
WHERE f.board_id = 18429499488 AND f.item_id = :item_id
GROUP BY f.item_id, f.status_id, s.status_label
ORDER BY min(f.status_start_utc), f.status_id;

-- 4. Indicadores atuais do projeto. NULL significa desconhecido, não zero.
SELECT i.item_id, i.item_name, r.status_atual, r.is_active,
       r.sla_start_utc, r.sla_start_quality, r.finalizado_em,
       r.lead_time_total_min / 60.0 AS horas_desde_entrada,
       r.sla_status_atual_min / 60.0 AS horas_status_atual,
       r.history_quality, r.atualizado_em AS corte_utc
FROM rede_globo.fct_item_sla_summary r
JOIN rede_globo.dim_item i USING (item_id, board_id)
WHERE r.board_id = 18429499488 AND r.item_id = :item_id;

-- 5. Lacunas e inconsistências que precisam acompanhar a análise do projeto.
SELECT code, detail, detected_at
FROM rede_globo.data_quality_issue
WHERE board_id = 18429499488 AND item_id = :item_id
ORDER BY code;

-- 6. Comparar etapas por visitas observadas e encerradas (amostra disponível).
-- Não mistura visitas ainda em andamento, inferências nem cadeias inconsistentes.
-- Não representa o histórico completo de todos os projetos do quadro.
SELECT s.status_label AS etapa, count(*) AS visitas_encerradas,
       count(DISTINCT f.item_id) AS projetos,
       avg(f.duration_hours) AS media_horas,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.duration_hours) AS mediana_horas,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY f.duration_hours) AS p95_horas,
       sum(f.duration_hours) AS horas_acumuladas
FROM rede_globo.fct_item_status_interval f
JOIN rede_globo.dim_status s USING (status_id, board_id)
WHERE f.board_id = 18429499488
  AND f.history_quality = 'observed' AND NOT f.is_open_interval
  AND f.event_end_id IS NOT NULL AND NOT s.is_terminal
  AND NOT EXISTS (
      SELECT 1 FROM rede_globo.data_quality_issue q
      WHERE q.board_id = f.board_id AND q.item_id = f.item_id
        AND q.code = 'cadeia_status_inconsistente'
  )
GROUP BY f.status_id, s.status_label
ORDER BY mediana_horas DESC;

-- 7. Fila atual: contagem separada do tempo dos projetos já encerrados.
-- Idade só entra na média se início observado e status atual reconciliado.
SELECT s.status_label AS etapa, count(*) AS projetos_na_fila,
       count(*) FILTER (WHERE f.history_quality = 'observed'
           AND r.sla_status_atual_min IS NOT NULL) AS projetos_com_idade_observada,
       avg(r.sla_status_atual_min / 60.0) FILTER
           (WHERE f.history_quality = 'observed') AS idade_media_observada_horas,
       max(r.sla_status_atual_min / 60.0) FILTER
           (WHERE f.history_quality = 'observed') AS maior_idade_observada_horas
FROM rede_globo.dim_item i
JOIN rede_globo.dim_status s ON s.status_id = i.current_status_id
JOIN rede_globo.fct_item_sla_summary r ON r.item_id = i.item_id AND r.board_id = i.board_id
LEFT JOIN rede_globo.fct_item_status_interval f
  ON f.item_id = i.item_id AND f.board_id = i.board_id
 AND f.status_id = i.current_status_id AND f.is_open_interval
WHERE i.board_id = 18429499488 AND i.is_active AND NOT s.is_terminal
GROUP BY s.status_id, s.status_label
ORDER BY projetos_na_fila DESC;

-- 8. Atualização e corte efetivos. Não é um fechamento D+1 implementado.
SELECT pipeline_name, last_run_utc AS corte_utc, updated_at AS watermark_gravado_em
FROM rede_globo.etl_watermark WHERE board_id = 18429499488;
