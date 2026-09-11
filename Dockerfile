FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home pipeline \
    && mkdir /app/runtime && chown pipeline:pipeline /app/runtime
COPY sql ./sql
USER pipeline
ENTRYPOINT ["sla-pipeline"]
CMD ["loop"]
