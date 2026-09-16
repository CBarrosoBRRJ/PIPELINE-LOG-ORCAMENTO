from datetime import date
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    monday_api_token: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("MONDAY_API_TOKEN", "TOKEN_MONDAY")
    )
    monday_api_url: str = "https://api.monday.com/v2"
    monday_api_version: str = "2026-04"
    monday_board_id: int = Field(
        default=18429499488, validation_alias=AliasChoices("MONDAY_BOARD_ID", "BOARDS")
    )
    monday_status_column_id: str = Field(
        default="status_19", validation_alias=AliasChoices("MONDAY_STATUS_COLUMN_ID", "COLUNA")
    )
    status_column_labels_override: dict[str, str] = Field(default_factory=dict)
    business_columns_override: dict[str, str] = Field(default_factory=dict)
    final_status_labels: list[str] = Field(
        default_factory=lambda: ["Encerrado", "Declinado pelo Mercado", "Declinado Internamente"]
    )
    initial_status_label: str = "Entrada"
    preferred_timezone: str = "America/Sao_Paulo"
    run_window_hours: int = Field(default=24, ge=1)
    overlap_minutes: int = Field(default=30, ge=0)
    backfill_from: str = "2000-01-01T00:00:00Z"
    activity_window_days: int = Field(default=30, ge=1)
    monday_page_size: int = Field(default=100, ge=1, le=500)
    monday_log_page_size: int = Field(default=100, ge=1, le=1000)
    monday_timeout_seconds: int = Field(default=60, ge=1)
    monday_max_retries: int = Field(default=6, ge=0, le=15)
    target_db: Literal["bigquery"] = "bigquery"
    pg_dsn: SecretStr = SecretStr("")
    pg_host: str = "127.0.0.1"
    pg_port: int = 55432
    pg_db: str = "sla_workflow"
    pg_user: str = "sla_pipeline"
    pg_password: SecretStr = SecretStr("")
    pg_schema: str = "orcamento"
    pg_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = (
        "prefer"
    )
    bq_project: str = ""
    bq_dataset: str = "viu_agenciamento"
    bq_table: str = "sla_orcamento"
    bq_location: str = "US"
    bq_keyfile: str = ""
    gcs_bucket: str = ""
    gcs_prefix: str = "sla_orcamento"
    bq_job_timeout_seconds: int = Field(default=1200, ge=1)
    business_holidays: list[date] = Field(default_factory=list)
    runtime_dir: Path = Path("runtime")

    @field_validator("final_status_labels")
    @classmethod
    def configured_finals(cls, value):
        if not value or any(not label.strip() for label in value):
            raise ValueError("Configure FINAL_STATUS_LABELS com os status finais do processo")
        return value

    @field_validator("monday_board_id", mode="before")
    @classmethod
    def legacy_board(cls, value):
        if isinstance(value, str):
            value = value.strip().strip("[]").strip().strip("'\"")
        return value

    @field_validator("pg_schema", "bq_dataset", "bq_table")
    @classmethod
    def identifier(cls, value):
        import re

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("Identificador de schema/dataset inválido")
        return value

    @field_validator("gcs_prefix")
    @classmethod
    def storage_prefix(cls, value):
        import re

        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", value):
            raise ValueError("Prefixo Cloud Storage inválido")
        return value

    @field_validator("pg_schema")
    @classmethod
    def canonical_budget_schema(cls, value):
        # Explicit compatibility for the renamed provisional deployment.
        # Prevent an older EasyPanel variable from recreating a second schema.
        return "orcamento" if value == "orcamentos" else value

    @field_validator("preferred_timezone")
    @classmethod
    def timezone(cls, value):
        ZoneInfo(value)
        return value

    @property
    def pipeline_name(self):
        return f"sls_orcamento_pdd:{self.monday_board_id}:{self.monday_status_column_id}"


def load_settings(env_file=".env"):
    """Reject ambiguous pasted configuration without displaying secret values."""
    from dotenv.parser import parse_stream

    path = Path(env_file)
    if not path.is_file():
        # Docker/managed runners inject variables without copying secrets into the image.
        if str(env_file) == ".env":
            return Settings(_env_file=None)
        raise ValueError("Arquivo de configuração informado não encontrado")
    seen = set()
    with path.open(encoding="utf-8") as handle:
        for binding in parse_stream(handle):
            if binding.error:
                raise ValueError(
                    f"Sintaxe inválida no .env, linha {binding.original.line}; use CHAVE=valor e comentários com #"
                )
            if binding.key:
                if binding.key in seen:
                    raise ValueError(
                        f"Chave duplicada no .env: {binding.key}; mantenha uma única configuração ativa"
                    )
                if binding.key in {
                    "DB_HOST",
                    "DB_PORT",
                    "DB_NAME",
                    "DB_USER",
                    "DB_PASSWORD",
                    "DB_SCHEMA",
                }:
                    raise ValueError(
                        f"Chave não utilizada pelo pipeline: {binding.key}; configure os campos PG_*"
                    )
                seen.add(binding.key)
    return Settings(_env_file=env_file)
