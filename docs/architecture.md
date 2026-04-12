# Architecture

## Request flow (video)

```mermaid
sequenceDiagram
  participant Browser
  participant Nginx
  participant API as FastAPI
  participant DB as PostgreSQL_or_SQLite
  participant Redis
  participant Worker as Celery_worker
  participant Storage

  Browser->>Nginx: POST /api/analyze-video
  Nginx->>API: proxy
  API->>Storage: save upload
  API->>DB: create job, upload_key
  API->>Redis: enqueue process_analysis_task
  API-->>Browser: job_id, QUEUED

  Worker->>DB: load job
  Worker->>Worker: MTCNN, EfficientNet, aggregation, GradCAM
  Worker->>DB: save result, COMPLETED
  Worker->>Redis: Socket.io emit analysis_update

  Browser->>Nginx: GET /api/results/job_id
  Nginx->>API: proxy
  API->>DB: read job + result
  API-->>Browser: state, stage, progress, result
```

## Components

- **API** (`backend/app/main.py`): FastAPI + Socket.io (Redis manager) for optional live updates from workers.
- **Worker** (`docker-compose` service `worker`): Celery executes `process_analysis_task` in `backend/app/api/routes/analyze.py`.
- **Persistence**: Jobs and results via SQLAlchemy (`backend/app/db/`). Engine URL from `DATABASE_URL` or SQLite file.
- **Artifacts**: Files under configurable storage dir; served via `/api/artifacts/...`.

## Why two databases?

- **SQLite**: zero-setup local development.
- **PostgreSQL**: shared state between API and multiple workers in Docker.

## Related docs

- [API.md](API.md) — endpoint summary
- [ML_EVALUATION.md](ML_EVALUATION.md) — offline evaluation
