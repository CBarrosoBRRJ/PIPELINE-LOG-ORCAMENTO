def get_store(settings):
    from .bq import BigQueryStore

    return BigQueryStore(settings)
