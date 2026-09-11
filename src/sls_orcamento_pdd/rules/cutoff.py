"""Closed-day consumption; preserve ingestion and actual capture timestamps."""

from collections import defaultdict
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo


def closed_day_cut(at, timezone):
    zone = ZoneInfo(timezone)
    return datetime.combine(at.astimezone(zone).date(), time.min, zone).astimezone(UTC)


def close_gold_day(rows, cutoff, timezone):
    """Keep passages starting before the exclusive midnight boundary.

    Source events and snapshots remain unchanged. Attributes are explicitly
    from cadastro_referencia_utc, potentially later than the metric cut.
    """
    grouped = defaultdict(list)
    for original in rows:
        if original["entrada_status_utc"] < cutoff:
            grouped[original["item_id"]].append(dict(original))
    result = []
    for passages in grouped.values():
        passages.sort(key=lambda r: r["ordem_etapa"])
        last = passages[-1]
        # A transition at midnight belongs to the next day's publication.
        last.update(
            saida_status_utc=None,
            saida_status_local=None,
            intervalo_aberto=True,
            elegivel_comparacao=False,
            horas_observadas_encerradas=None,
        )
        last["duracao_minutos"] = (cutoff - last["entrada_status_utc"]).total_seconds() / 60
        last["duracao_horas"] = last["duracao_minutos"] / 60
        start = last["entrada_comprovada_utc"]
        if start is not None and start >= cutoff:
            start = None
        finished = (
            last["entrada_status_utc"]
            if last["status_final"] and last["qualidade_historico"] == "observed"
            else None
        )
        inconsistent = last["status_atual_divergente"]
        # If source state disagrees, a historical last event is not proof of
        # the missing transition. Keep its duration, but leave current age null.
        total = (
            ((finished or cutoff) - start).total_seconds() / 3600
            if start is not None
            and (not last["status_final"] or finished is not None)
            and not inconsistent
            else None
        )
        for index, row in enumerate(passages, 1):
            row.update(
                corte_utc=cutoff,
                corte_local=cutoff.astimezone(ZoneInfo(timezone)).replace(tzinfo=None),
                eh_ultimo_registro=index == len(passages),
                status_atual_id=last["status_id"],
                status_atual_nome=last["status_nome"],
                projeto_na_fila=row["projeto_ativo"] and not last["status_final"],
                entrada_comprovada_utc=start,
                finalizado_em_utc=finished,
                tempo_desde_entrada_horas=total,
                tempo_status_atual_horas=None if inconsistent else last["duracao_horas"],
            )
            result.append(row)
    return result
