-- Executar só após backup/restore e mudança do Power BI para gold_projeto_status.
-- Remoção autorizada das saídas analíticas substituídas. Sem CASCADE.
-- initialize() da versão >=2.1.0 não recria essas views.
BEGIN;
SET LOCAL lock_timeout = '10s';
DROP VIEW IF EXISTS orcamento.gold_status_bottlenecks;
DROP VIEW IF EXISTS orcamento.gold_status_metrics;
DROP VIEW IF EXISTS orcamento.gold_project_status;
DROP VIEW IF EXISTS orcamento.gold_intervals_local;
COMMIT;
