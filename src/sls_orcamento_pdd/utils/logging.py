import json
import logging

from .time import utcnow


def emit(event, **fields):
    print(
        json.dumps(
            {"timestamp": utcnow().isoformat(), "event": event, **fields},
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )


def configure_logging():
    logging.basicConfig(level=logging.WARNING)
