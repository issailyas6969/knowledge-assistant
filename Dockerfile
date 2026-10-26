FROM python:3.12-slim

RUN useradd -m app && mkdir /data && chown app:app /data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

USER app
# download the embedding model at build time so start-up is fast and works offline
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warm up'])" || true

# all data (accounts, tickets, documents, vector index) lives in /data, which is a Docker volume
WORKDIR /data
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["/app/entrypoint.sh"]
