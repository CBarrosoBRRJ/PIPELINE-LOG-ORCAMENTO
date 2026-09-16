"""Offline checks for deployment files; never load the user's .env or contact GCP."""

import ast
import json
from pathlib import Path

import pytest

from sls_orcamento_pdd.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_managed_configuration_matches_the_confirmed_destination():
    values = {}
    for line in (ROOT / "deploy/gcp.env.yaml").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, value = line.split(":", 1)
            values[name] = ast.literal_eval(value.strip())
    # BaseSettings decodes env JSON; init kwargs must already carry their native types.
    for name in ("BUSINESS_HOLIDAYS", "FINAL_STATUS_LABELS"):
        values[name.lower()] = json.loads(values.pop(name))
    aliases = {"MONDAY_BOARD_ID", "MONDAY_STATUS_COLUMN_ID"}
    kwargs = {k if k in aliases else k.lower(): v for k, v in values.items()}
    settings = Settings(_env_file=None, **kwargs)
    assert settings.target_db == "bigquery"
    assert settings.bq_project == "gglobo-viu-dados-hdg-prd"
    assert settings.bq_dataset == "viu_agenciamento"
    assert settings.bq_table == "sla_orcamento"
    assert settings.bq_location == "US"
    assert settings.monday_board_id == 18429499488
    assert settings.monday_status_column_id == "status_19"
    assert settings.preferred_timezone == "America/Sao_Paulo"
    assert settings.gcs_bucket == "__SET_AT_DEPLOY__"
    assert "MONDAY_API_TOKEN" not in values
    assert not any(k.startswith("PG_") for k in values)


@pytest.mark.parametrize("filename", [".gitignore", ".dockerignore", ".gcloudignore"])
def test_private_infrastructure_artifacts_are_excluded(filename):
    patterns = (ROOT / filename).read_text(encoding="utf-8").splitlines()
    assert ".env" in patterns
    assert "*.tfplan" in patterns
    assert "*.tfvars.json" in patterns
    assert any(p.startswith("*.tfstate") for p in patterns)


def test_container_runs_job_and_does_not_copy_env():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copies = [line for line in dockerfile.splitlines() if line.startswith("COPY ")]
    assert copies == ["COPY pyproject.toml ./", "COPY src ./src", "COPY sql ./sql"]
    assert 'ENTRYPOINT ["sla-pipeline"]' in dockerfile
    assert 'CMD ["daily"]' in dockerfile
    assert "USER pipeline" in dockerfile
    deploy = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    assert "__SET_AT_DEPLOY__" in deploy
    assert "--set-secrets" in deploy
    assert "--execute-now" not in deploy
    schedule = (ROOT / "deploy/schedule.sh").read_text(encoding="utf-8")
    assert "--schedule '0 6 * * *' --time-zone America/Sao_Paulo" in schedule
