-- Existing databases: run sla-pipeline init-db first. It adds/backfills UUIDv5 SKs transactionally without extensions.

-- Reference DDL for constraints after columns and UUIDv5 data migration. No tables are dropped.

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_board_identity'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_board ADD CONSTRAINT uq_dim_board_identity UNIQUE (board_id, board_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_board_surrogate'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_board ADD CONSTRAINT uq_dim_board_surrogate UNIQUE (board_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_status_identity'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_status ADD CONSTRAINT uq_dim_status_identity UNIQUE (status_id, status_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_status_surrogate'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_status ADD CONSTRAINT uq_dim_status_surrogate UNIQUE (status_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_person_identity'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_person ADD CONSTRAINT uq_dim_person_identity UNIQUE (person_id, person_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_person_surrogate'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_person ADD CONSTRAINT uq_dim_person_surrogate UNIQUE (person_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_item_identity'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_item ADD CONSTRAINT uq_dim_item_identity UNIQUE (item_id, item_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_dim_item_surrogate'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_item ADD CONSTRAINT uq_dim_item_surrogate UNIQUE (item_sk);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_meta_gold_rule_snapsho_54d2df14'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.meta_gold_rule_snapshot ADD CONSTRAINT fk_meta_gold_rule_snapsho_54d2df14 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_meta_entity_mapping_c3348c56'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.meta_entity_mapping ADD CONSTRAINT fk_meta_entity_mapping_c3348c56 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_gold_projeto_status_15cb5839'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_gold_projeto_status_15cb5839 FOREIGN KEY(status_atual_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_gold_projeto_status_3e6fde19'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_gold_projeto_status_3e6fde19 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_gold_projeto_status_a35625af'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_gold_projeto_status_a35625af FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_gold_projeto_status_d612ad30'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_gold_projeto_status_d612ad30 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_gold_projeto_status_f2b260a7'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_gold_projeto_status_f2b260a7 FOREIGN KEY(interval_id) REFERENCES sladb.fct_item_status_interval (interval_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_gold_projeto_status_fec14abf'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_gold_projeto_status_fec14abf FOREIGN KEY(versao_regras) REFERENCES sladb.meta_gold_rule_snapshot (versao_regras) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_gold_projeto_status_2e6468b2'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_sk_gold_projeto_status_2e6468b2 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_gold_projeto_status_60f72d33'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_sk_gold_projeto_status_60f72d33 FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_gold_projeto_status_6758164f'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.gold_projeto_status ADD CONSTRAINT fk_sk_gold_projeto_status_6758164f FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_meta_column_mapping_0a689ea5'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.meta_column_mapping ADD CONSTRAINT fk_meta_column_mapping_0a689ea5 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_meta_column_mapping_e946c5b7'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.meta_column_mapping ADD CONSTRAINT fk_sk_meta_column_mapping_e946c5b7 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bronze_monday_activity_3dcc3f5c'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bronze_monday_activity_log_raw ADD CONSTRAINT fk_bronze_monday_activity_3dcc3f5c FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bronze_monday_activity_b0f7a30e'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bronze_monday_activity_log_raw ADD CONSTRAINT fk_bronze_monday_activity_b0f7a30e FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bronze_monday_item_sna_24cd51e8'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bronze_monday_item_snapshot_raw ADD CONSTRAINT fk_bronze_monday_item_sna_24cd51e8 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bronze_monday_item_sna_a359096f'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bronze_monday_item_snapshot_raw ADD CONSTRAINT fk_bronze_monday_item_sna_a359096f FOREIGN KEY(current_status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bronze_monday_item_sna_d0aabd55'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bronze_monday_item_snapshot_raw ADD CONSTRAINT fk_bronze_monday_item_sna_d0aabd55 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bronze_monday_board_sc_6408c39c'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bronze_monday_board_schema_raw ADD CONSTRAINT fk_bronze_monday_board_sc_6408c39c FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_silver_monday_status_e_b21a1cfe'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_silver_monday_status_e_b21a1cfe FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_silver_monday_status_e_b5769ee2'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_silver_monday_status_e_b5769ee2 FOREIGN KEY(event_id) REFERENCES sladb.bronze_monday_activity_log_raw (event_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_silver_monday_status_e_ba5ffa81'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_silver_monday_status_e_ba5ffa81 FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_silver_monday_status_e_d1373af0'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_silver_monday_status_e_d1373af0 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_silver_monday_statu_1b1d6d34'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_sk_silver_monday_statu_1b1d6d34 FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_silver_monday_statu_275d8684'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_sk_silver_monday_statu_275d8684 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_silver_monday_statu_b0d4ce85'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.silver_monday_status_event_stg ADD CONSTRAINT fk_sk_silver_monday_statu_b0d4ce85 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_dim_status_ab14a9c2'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_status ADD CONSTRAINT fk_dim_status_ab14a9c2 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_dim_status_f64c46d4'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_status ADD CONSTRAINT fk_sk_dim_status_f64c46d4 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_dim_item_09337c7f'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_item ADD CONSTRAINT fk_dim_item_09337c7f FOREIGN KEY(current_status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_dim_item_d11a0832'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_item ADD CONSTRAINT fk_dim_item_d11a0832 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_dim_item_90ad47c4'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_item ADD CONSTRAINT fk_sk_dim_item_90ad47c4 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_dim_item_dd30ed1b'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.dim_item ADD CONSTRAINT fk_sk_dim_item_dd30ed1b FOREIGN KEY(current_status_id, current_status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bridge_item_person_7129f07e'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bridge_item_person ADD CONSTRAINT fk_bridge_item_person_7129f07e FOREIGN KEY(person_id) REFERENCES sladb.dim_person (person_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bridge_item_person_781d0b8e'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bridge_item_person ADD CONSTRAINT fk_bridge_item_person_781d0b8e FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_bridge_item_person_81549e59'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bridge_item_person ADD CONSTRAINT fk_bridge_item_person_81549e59 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_bridge_item_person_12f60f40'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bridge_item_person ADD CONSTRAINT fk_sk_bridge_item_person_12f60f40 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_bridge_item_person_cbc0d895'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bridge_item_person ADD CONSTRAINT fk_sk_bridge_item_person_cbc0d895 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_bridge_item_person_d42f7eec'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.bridge_item_person ADD CONSTRAINT fk_sk_bridge_item_person_d42f7eec FOREIGN KEY(person_id, person_sk) REFERENCES sladb.dim_person (person_id, person_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_interv_189ab117'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_fct_item_status_interv_189ab117 FOREIGN KEY(event_end_id) REFERENCES sladb.bronze_monday_activity_log_raw (event_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_interv_607c39b9'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_fct_item_status_interv_607c39b9 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_interv_77e9239a'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_fct_item_status_interv_77e9239a FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_interv_91c75244'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_fct_item_status_interv_91c75244 FOREIGN KEY(event_start_id) REFERENCES sladb.bronze_monday_activity_log_raw (event_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_interv_972db58d'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_fct_item_status_interv_972db58d FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_status_int_20069069'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_sk_fct_item_status_int_20069069 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_status_int_3d0ce0b1'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_sk_fct_item_status_int_3d0ce0b1 FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_status_int_4139de9f'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_interval ADD CONSTRAINT fk_sk_fct_item_status_int_4139de9f FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_daily_22189c08'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_daily ADD CONSTRAINT fk_fct_item_status_daily_22189c08 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_daily_9be8110c'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_daily ADD CONSTRAINT fk_fct_item_status_daily_9be8110c FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_status_daily_d19775a0'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_daily ADD CONSTRAINT fk_fct_item_status_daily_d19775a0 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_status_dai_2e645de9'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_daily ADD CONSTRAINT fk_sk_fct_item_status_dai_2e645de9 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_status_dai_6c37dcfb'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_daily ADD CONSTRAINT fk_sk_fct_item_status_dai_6c37dcfb FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_status_dai_72627477'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_status_daily ADD CONSTRAINT fk_sk_fct_item_status_dai_72627477 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_sla_summary_4edf7f62'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_sla_summary ADD CONSTRAINT fk_fct_item_sla_summary_4edf7f62 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_fct_item_sla_summary_c37db9ad'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_sla_summary ADD CONSTRAINT fk_fct_item_sla_summary_c37db9ad FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_sla_summar_3213dfd6'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_sla_summary ADD CONSTRAINT fk_sk_fct_item_sla_summar_3213dfd6 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_sk_fct_item_sla_summar_4e697322'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.fct_item_sla_summary ADD CONSTRAINT fk_sk_fct_item_sla_summar_4e697322 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_etl_watermark_5c17326e'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.etl_watermark ADD CONSTRAINT fk_etl_watermark_5c17326e FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_etl_run_06572f90'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.etl_run ADD CONSTRAINT fk_etl_run_06572f90 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_data_quality_issue_046237d0'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.data_quality_issue ADD CONSTRAINT fk_data_quality_issue_046237d0 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_data_quality_issue_703437c1'
                AND connamespace='sladb'::regnamespace) THEN
    ALTER TABLE sladb.data_quality_issue ADD CONSTRAINT fk_data_quality_issue_703437c1 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;