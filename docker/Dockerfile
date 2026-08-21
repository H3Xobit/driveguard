FROM python:3.11-slim-bookworm

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir -e . \
    && chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV DG_OFFLINE_LLM=1

EXPOSE 8000
CMD ["/entrypoint.sh"]
