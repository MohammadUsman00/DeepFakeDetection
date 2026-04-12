# HTTP API

Base path: **`/api`** (Nginx may expose the app on a single port; paths stay the same).

## `GET /api/health`

Returns service status and version fields (see OpenAPI).

## `POST /api/analyze-video`

- **Content-Type**: `multipart/form-data`
- **Field**: `file` — video file (see allowed extensions/MIME in config)

**Response (200)**: JSON including `job_id`, initial `state`, `stage`, `progress_percent`.

Errors: standardized JSON with `error` object and `request_id` (see global exception handlers).

## `POST /api/analyze-image`

Same pattern as video; validation enforces image types.

## `GET /api/results/{job_id}`

Returns:

- `state`: e.g. `QUEUED`, `RUNNING`, `PROCESSING`, `COMPLETED`, `FAILED`
- `stage`: processing stage string
- `progress_percent`: 0–100
- `result`: opaque JSON summary when completed (scores, labels, `top_k_suspicious`, etc.)
- `error`: populated when failed

## `GET /api/artifacts/{job_id}/{name}`

Serves a stored artifact (e.g. PNG heatmap). Paths are validated server-side.

## Discovery

Swagger UI: **`/api/docs`**  
OpenAPI JSON: **`/api/openapi.json`**
