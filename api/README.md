# API Layer

The API layer exposes the compliance stack over HTTP using FastAPI.

## Endpoints

- `POST /query`
- `POST /ingest`
- `GET /sources`
- `GET /health`
- `GET /config`
- `DELETE /sources/{source_id}`

## Run locally

```bash
uvicorn api.main:app --reload
```

The API uses environment-driven configuration from the project root `.env`.

## Observability

The API emits structured request logs and a request correlation header.

- `LOG_LEVEL` controls verbosity (default `INFO`).
- `LOG_FORMAT` controls output format (`json` or `text`, default `json`).
- Each response includes `X-Request-Id` for tracing across logs.
