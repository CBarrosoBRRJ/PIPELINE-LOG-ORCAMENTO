from .runner import run


def daily_run(settings):
    return run(settings, "daily")
