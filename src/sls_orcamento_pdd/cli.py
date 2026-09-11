import argparse
import json
import sys

from .config import load_settings
from .utils.logging import emit


def main():
    parser = argparse.ArgumentParser(description="SLA Monday — sls_orcamento_pdd")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "command",
        choices=[
            "discover",
            "init-db",
            "backfill",
            "daily",
            "loop",
            "replay",
            "preview-gold",
            "validate",
            "validate-gold",
            "health",
            "export-bq",
            "check-db",
            "quality-profile",
        ],
    )
    args = parser.parse_args()
    try:
        settings = load_settings(args.env_file)
        if args.command == "discover":
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

            report = quality_profile(get_store(settings), settings.monday_board_id)
            settings.runtime_dir.mkdir(parents=True, exist_ok=True)
            path = settings.runtime_dir / f"quality_{settings.monday_board_id}.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            emit(
                "quality_profile",
                tables=len(report["tables"]),
                critical_failures=report["critical_failures"],
            )
            if report["critical_failures"]:
                raise ValueError(
                    "Contrato inválido em uma ou mais tabelas; confira o relatório de qualidade em runtime"
                )
        elif args.command == "check-db":
            from .db.postgres import PostgresStore

            print(
                json.dumps(PostgresStore(settings).check_connection(), ensure_ascii=False, indent=2)
            )
        elif args.command == "init-db":
            from .db import get_store

            get_store(settings).initialize()
            emit("database_initialized", target=settings.target_db)
        elif args.command in ("daily", "backfill"):
            from .pipelines.runner import run
            from .utils.time import utcnow

            run(settings, args.command, scheduled_for=utcnow() if args.command == "daily" else None)
        elif args.command == "loop":
            from .pipelines.runner import run
            from .services.scheduler import run_loop

            run_loop(settings, run, emit)
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
            payload = (
                store.read_many(names, settings.monday_board_id)
                if hasattr(store, "read_many")
                else {n: store.read(n, settings.monday_board_id) for n in names}
            )
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
            payload = (
                store.read_many(names, settings.monday_board_id)
                if hasattr(store, "read_many")
                else {n: store.read(n, settings.monday_board_id) for n in names}
            )
            if not payload["dim_item"]:
                raise ValueError("Banco ainda sem itens")
            validate(payload, sum(i["is_active"] for i in payload["dim_item"]))
            emit("validation_success", items=len(payload["dim_item"]))
        elif args.command == "health":
            from .utils.time import parse_timestamp, utcnow

            path = settings.runtime_dir / f"status_{settings.monday_board_id}.json"
            status = json.loads(path.read_text(encoding="utf-8"))
            age = (utcnow() - parse_timestamp(status["end_at"])).total_seconds() / 3600
            if status["status"] != "success" or age > settings.run_window_hours + 2:
                raise ValueError("Última execução falhou ou está atrasada")
            emit("health_ok", age_hours=round(age, 2))
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
