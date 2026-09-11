-- PostgreSQL v3: reference uniqueness only. Internal references are validated in Python.

-- Legacy migration: sla-pipeline migrate-single-table. Never recreate technical tables.

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_gold_projeto_ordem'
                AND connamespace='orcamento'::regnamespace) THEN
    ALTER TABLE orcamento.gold_projeto_status ADD CONSTRAINT uq_gold_projeto_ordem UNIQUE (board_id, item_id, ordem_etapa);
  END IF;
END $$;