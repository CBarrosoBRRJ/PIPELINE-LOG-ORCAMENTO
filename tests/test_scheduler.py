from datetime import UTC, datetime

import pytest

from sls_orcamento_pdd.config import Settings
from sls_orcamento_pdd.services.scheduler import daily_schedule, next_daily_run, run_cycle


@pytest.mark.parametrize(
    "schedule", ["*/5 * * * *", "0 6 * * 1", "60 6 * * *", "0 24 * * *", "0 6"]
)
def test_rejects_unsupported_schedule(schedule):
    with pytest.raises(ValueError):
        daily_schedule(schedule)


def test_six_sao_paulo_is_nine_utc_and_passed_hour_waits_tomorrow():
    assert next_daily_run(
        datetime(2026, 9, 11, 8, tzinfo=UTC), "0 6 * * *", "America/Sao_Paulo"
    ) == datetime(2026, 9, 11, 9, tzinfo=UTC)
    assert next_daily_run(
        datetime(2026, 9, 11, 9, tzinfo=UTC), "0 6 * * *", "America/Sao_Paulo"
    ) == datetime(2026, 9, 12, 9, tzinfo=UTC)


def test_failure_log_never_echoes_exception_values(settings):
    events = []

    def failing_runner(*args, **kwargs):
        raise RuntimeError("password=private-secret SQL parameters confidential")

    assert not run_cycle(
        settings, failing_runner, lambda event, **fields: events.append((event, fields))
    )
    assert events == [("loop_run_failed", {"error_type": "RuntimeError"})]


def test_process_defaults_have_finals_and_explicit_empty_is_rejected():
    settings = Settings(_env_file=None)
    assert "Encerrado" in settings.final_status_labels
    with pytest.raises(ValueError):
        Settings(_env_file=None, final_status_labels=[])


def test_old_deployment_schema_resolves_to_canonical_name():
    assert Settings(_env_file=None, pg_schema="orcamentos").pg_schema == "orcamento"
    assert Settings(_env_file=None, pg_schema="financeiro").pg_schema == "financeiro"


def test_restart_waits_until_schedule_before_calling_runner(settings, monkeypatch):
    import sls_orcamento_pdd.services.scheduler as scheduler

    class Clock:
        current = datetime(2026, 9, 11, 8, tzinfo=UTC)

        @classmethod
        def now(cls, tz):
            return cls.current

    calls = []

    def sleep(seconds):
        assert not calls
        Clock.current = datetime(2026, 9, 11, 9, tzinfo=UTC)

    def runner(*args, **kwargs):
        calls.append(kwargs["scheduled_for"])
        raise KeyboardInterrupt

    monkeypatch.setattr(scheduler, "datetime", Clock)
    monkeypatch.setattr("time.sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        scheduler.run_loop(settings, runner, lambda *args, **kwargs: None)
    assert calls == [datetime(2026, 9, 11, 9, tzinfo=UTC)]
