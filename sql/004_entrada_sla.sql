-- Migração aditiva; executada automaticamente pelo initialize do store.
ALTER TABLE sladb.fct_item_sla_summary
  ADD COLUMN IF NOT EXISTS sla_start_utc TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS sla_start_quality TEXT;
-- Execute replay após aplicar para recalcular o SLA iniciado em Entrada.
