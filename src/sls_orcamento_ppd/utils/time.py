from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation


def utcnow():
    return datetime.now(UTC)


def parse_timestamp(value) -> datetime:
    """Monday created_at: Unix seconds * 10^7 (17 digits), NOT milliseconds.

    Decimal avoids float precision loss. Also accepts Unix s/ms/us/ns and ISO8601.
    Naive ISO timestamps are rejected rather than silently applying local time.
    """
    if isinstance(value, datetime):
        result = value
    elif value is None or value == "":
        raise ValueError("Timestamp ausente")
    else:
        raw = str(value).strip()
        try:
            number = Decimal(raw)
        except InvalidOperation:
            try:
                result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                # The builtin error includes the rejected input, which may be private.
                raise ValueError("Timestamp ISO8601 inválido; valor omitido") from None
        else:
            if not number.is_finite():
                raise ValueError("Timestamp não finito")
            digits = len(raw.split(".")[0].lstrip("-+"))
            scale = {10: 1, 13: 1000, 16: 1_000_000, 17: 10_000_000, 19: 1_000_000_000}
            if digits not in scale:
                raise ValueError(f"Precisão Unix não suportada: {digits}")
            result = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                microseconds=int(number * 1_000_000 / scale[digits])
            )
    if result.tzinfo is None:
        raise ValueError("Timestamp sem timezone")
    result = result.astimezone(UTC)
    if not 2000 <= result.year <= 2100:
        raise ValueError("Timestamp fora do intervalo seguro 2000–2100")
    return result


def event_timestamp(data, native):
    value = data.get("value") or {}
    if isinstance(value, str):
        import json

        value = json.loads(value)
    for candidate in (
        value.get("changed_at") if isinstance(value, dict) else None,
        data.get("changed_at"),
    ):
        if candidate:
            try:
                return parse_timestamp(candidate), "changed_at"
            except (ValueError, TypeError, OverflowError):
                pass
    return parse_timestamp(native), "created_at_native"


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
