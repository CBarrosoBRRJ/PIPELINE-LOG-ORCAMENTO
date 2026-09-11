"""Small daily scheduler for the temporary EasyPanel executor."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def daily_schedule(expression):
    fields = expression.split()
    if len(fields) != 5 or fields[2:] != ["*", "*", "*"]:
        raise ValueError("loop aceita apenas horário diário fixo: MINUTO HORA * * *")
    try:
        minute, hour = (int(value) for value in fields[:2])
    except ValueError:
        raise ValueError("loop exige minuto e hora inteiros") from None
    if not 0 <= minute <= 59 or not 0 <= hour <= 23:
        raise ValueError("Horário diário inválido")
    return minute, hour


def next_daily_run(now, expression, timezone):
    minute, hour = daily_schedule(expression)
    local = now.astimezone(ZoneInfo(timezone))
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(UTC)


def run_cycle(settings, runner, emit, scheduled_for=None):
    try:
        report = runner(settings, "daily", scheduled_for=scheduled_for or datetime.now(UTC))
        emit("loop_run_skipped" if report.get("status") == "skipped" else "loop_run_success")
        return True
    except Exception as error:
        # Driver exceptions may contain SQL, parameters or credentials.
        # runner already persists failed health state; never echo raw exceptions.
        emit("loop_run_failed", error_type=type(error).__name__)
        return False


def run_loop(settings, runner, emit):
    import time

    daily_schedule(settings.cron_schedule)  # Validate before making any API calls.
    emit("loop_started", schedule=settings.cron_schedule, tz=settings.preferred_timezone)
    while True:
        now = datetime.now(UTC)
        target = next_daily_run(now, settings.cron_schedule, settings.preferred_timezone)
        emit(
            "loop_sleeping",
            next_run=target.astimezone(ZoneInfo(settings.preferred_timezone)).isoformat(),
        )
        while (remaining := (target - datetime.now(UTC)).total_seconds()) > 0:
            time.sleep(min(60, remaining))
        run_cycle(settings, runner, emit, scheduled_for=target)
