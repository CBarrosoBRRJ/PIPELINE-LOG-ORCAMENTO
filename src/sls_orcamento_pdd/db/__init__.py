def get_store(settings):
    if settings.target_db == "bigquery":
        from .bq import BigQueryStore

        return BigQueryStore(settings)
    from .consumer import ConsumerStore

    return ConsumerStore(settings)
