"""Watermark lookup and private cloud execution reports."""


def write_status(settings, report, store):
    store.write_artifact("execution", report)


def watermark(rows, pipeline_name):
    return next((r for r in rows if r["pipeline_name"] == pipeline_name), None)
