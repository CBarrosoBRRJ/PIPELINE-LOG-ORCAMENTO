import argparse
import json
import sys

from .config import load_settings
from .utils.logging import emit


def main():
    parser = argparse.ArgumentParser(description="SLA Monday — sls_orcamento_ppd")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "command",
        choices=[
            "discover",
            "init-db",
            "backfill",
            "daily",
            "replay",
            "preview-gold",
            "validate",
            "validate-gold",
            "health",
            "export-bq",
            "check-db",
            "quality-profile",
            "export-review",
            "import-review",
            "backup-state",
            "import-state",
            "recover",
            "inspect-lock",
            "unlock",
            "calendar",
        ],
    )
    parser.add_argument("--review-file")
    parser.add_argument("--checkpoint-file")
    parser.add_argument("--generation")
    parser.add_argument("--lock-generation", type=int)
    parser.add_argument("--execution-stopped", action="store_true")
    parser.add_argument("--year", type=int)
    args = parser.parse_args()
    try:
        settings = load_settings(args.env_file)
        if args.command == "calendar":
            from datetime import datetime
            from zoneinfo import ZoneInfo

            from .rules.business_time import BusinessCalendar

            year = args.year or datetime.now().year
            zone = ZoneInfo(settings.preferred_timezone)
            calendar = BusinessCalendar(settings.preferred_timezone, settings.business_holidays)
            calendar.hours(
                datetime(year, 1, 1, tzinfo=zone), datetime(year, 12, 31, 23, tzinfo=zone)
            )
            print(json.dumps(calendar.snapshot(), ensure_ascii=False, indent=2))
        elif args.command in {"import-state", "recover", "inspect-lock", "unlock"}:
            from pathlib import Path

            from .db.bq import BigQueryStore
            from .migration.readers import load_checkpoint

            store = BigQueryStore(settings)
            if args.command == "inspect-lock":
                emit("gcs_lock", **store.objects.inspect_lock())
            elif args.command == "unlock":
                if not args.execution_stopped or not args.lock_generation:
                    raise ValueError(
                        "Pare a execução e informe --execution-stopped e --lock-generation"
                    )
                store.objects.unlock(args.lock_generation)
                emit("gcs_lock_removed", generation=args.lock_generation)
            elif args.command == "recover":
                store.initialize()
                emit("gcp_recovered", **store.check_connection())
            else:
                if not args.checkpoint_file or not args.generation:
                    raise ValueError(
                        "Informe --checkpoint-file e --generation do recibo PostgreSQL"
                    )
                data = load_checkpoint(Path(args.checkpoint_file), args.generation)
                emit("gcp_migration_verified", **store.import_state(data))
        elif args.command in {
            "export-review",
            "import-review",
            "backup-state",
        }:
            from .db import get_store
            from .services.review import export_review, import_review

            store = get_store(settings)
            if args.command == "export-review":
                emit("review_exported", **export_review(store, settings))
            elif args.command == "backup-state":
                emit("state_backup", uri=store.backup())
            else:
                if not args.review_file:
                    raise ValueError("Informe --review-file com o catálogo revisado")
                emit("review_imported", **import_review(store, settings, args.review_file))
        elif args.command == "discover":
            from .clients.monday_client import MondayClient
            from .services.extract import discover

            board = MondayClient(settings).board()
            mapping, statuses, _ = discover(board, settings)
            print(
                json.dumps(
                    {
                        "board_id": board["id"],
                        "name": board["name"],
                        "items_count": board["items_count"],
                        "mapping": mapping,
                        "statuses": statuses,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "quality-profile":
            from .db import get_store
            from .services.quality import quality_profile

            store = get_store(settings)
            report = quality_profile(store, settings.monday_board_id)
            emit("quality_report", uri=store.write_artifact("quality", report))
            emit(
                "quality_profile",
                tables=len(report["tables"]),
                critical_failures=report["critical_failures"],
            )
            if report["critical_failures"]:
                raise ValueError("Contrato inválido; confira o relatório de qualidade")
        elif args.command == "check-db":
            from .db import get_store

            print(json.dumps(get_store(settings).check_connection(), ensure_ascii=False, indent=2))
        elif args.command == "init-db":
            from .db import get_store

            get_store(settings).initialize()
            emit("database_initialized", target=settings.target_db)
        elif args.command in ("daily", "backfill"):
            from .pipelines.runner import run
            from .utils.time import utcnow

            run(settings, args.command, scheduled_for=utcnow() if args.command == "daily" else None)
        elif args.command in ("replay", "preview-gold"):
            from .pipelines.runner import replay

            replay(settings, publish=args.command == "replay")
        elif args.command == "validate-gold":
            from .db import get_store
            from .rules.cutoff import closed_day_cut
            from .services.gold import validate_gold
            from .services.state import watermark

            store = get_store(settings)
            names = [
                "gold_projeto_status",
                "quarentena_projeto",
                "fct_item_status_interval",
                "data_quality_issue",
                "etl_watermark",
            ]
            payload = store.read_many(names, settings.monday_board_id)
            if not payload["fct_item_status_interval"]:
                raise ValueError("Banco sem intervalos para reconciliar")
            previous = watermark(payload["etl_watermark"], settings.pipeline_name)
            cutoff = (
                closed_day_cut(previous["last_run_utc"], settings.preferred_timezone)
                if previous
                else None
            )
            validate_gold(payload, cutoff=cutoff)
            emit("gold_validation_success", rows=len(payload["gold_projeto_status"]))
        elif args.command == "validate":
            from .db import get_store
            from .services.transform import validate

            store = get_store(settings)
            names = ["dim_item", "fct_item_status_interval", "fct_item_status_daily"]
            payload = store.read_many(names, settings.monday_board_id)
            if not payload["dim_item"]:
                raise ValueError("Banco ainda sem itens")
            validate(payload, sum(i["is_active"] for i in payload["dim_item"]))
            emit("validation_success", items=len(payload["dim_item"]))
        elif args.command == "health":
            from .db import get_store
            from .services.health import check_health

            emit("health_ok", **check_health(get_store(settings), settings))
        else:
            from .db.bq import export_postgres

            export_postgres(settings)
        return 0
    except Exception as error:
        # Pydantic / driver errors may embed input values; redact by default.
        from .clients.monday_client import MondayError

        safe = (
            str(error)[:1000]
            if type(error) in (ValueError, RuntimeError, MondayError)
            else "Consulte configuração/conectividade; detalhes sensíveis omitidos"
        )
        emit("command_failed", error_type=type(error).__name__, error=safe)
        return 1


if __name__ == "__main__":
    sys.exit(main())
