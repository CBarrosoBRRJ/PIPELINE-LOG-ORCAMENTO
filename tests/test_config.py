import pytest

from sls_orcamento_ppd.config import load_settings


def test_duplicate_configuration_fails_without_secret(tmp_path):
    path = tmp_path / ".env"
    path.write_text("PG_PASSWORD=first-secret\nPG_PASSWORD=second-secret\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Chave duplicada") as error:
        load_settings(path)
    assert "first-secret" not in str(error.value)
    assert "second-secret" not in str(error.value)


def test_unsupported_db_prefix_is_not_silently_ignored(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DB_HOST=remote-server\n", encoding="utf-8")
    with pytest.raises(ValueError, match="PG_"):
        load_settings(path)


def test_pasted_prose_is_rejected_without_echoing_it(tmp_path):
    path = tmp_path / ".env"
    path.write_text("an invalid line with secret-value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="linha") as error:
        load_settings(path)
    assert "secret-value" not in str(error.value)


def test_remote_pg_configuration(tmp_path, monkeypatch):
    for key in ("PG_HOST", "PG_PORT", "PG_DB", "PG_SCHEMA"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "PG_HOST=remote-server\nPG_PORT=5433\nPG_DB=database\nPG_SCHEMA=analytics\n",
        encoding="utf-8",
    )
    settings = load_settings(path)
    assert settings.pg_host == "remote-server"
    assert settings.pg_port == 5433
    assert settings.pg_schema == "analytics"


def test_environment_only_container_configuration(tmp_path, monkeypatch):
    from sls_orcamento_ppd.config import load_settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PG_HOST", "database.internal")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_DB", "dados_globo")
    settings = load_settings()
    assert settings.pg_host == "database.internal"
    assert settings.pg_port == 5432
    assert settings.pg_db == "dados_globo"


def test_gcp_only_default_and_no_implicit_postgres_fallback():
    from sls_orcamento_ppd.config import Settings

    assert Settings(_env_file=None).target_db == "bigquery"
    with pytest.raises(ValueError):
        Settings(_env_file=None, target_db="postgres")
    with pytest.raises(ValueError):
        Settings(_env_file=None, final_status_labels=[])
