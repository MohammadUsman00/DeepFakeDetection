# Freemium SaaS mode

## Overview

- **Users** table with email + bcrypt password.
- **JWT** access tokens (`Authorization: Bearer <token>`).
- **Jobs** are linked to `user_id` when authenticated.
- **Free tier**: daily upload cap (`SAAS_FREE_DAILY_UPLOADS`, UTC midnight reset). **`pro`** tier skips the cap (placeholder for billing later).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `SAAS_REQUIRE_AUTH` | `false` | If `true`, all uploads and result/artifact reads require a valid JWT (except health/docs). |
| `SAAS_JWT_SECRET` | dev placeholder | **Must be set to a long random string in production.** |
| `SAAS_JWT_EXP_HOURS` | `168` | Token lifetime (hours). |
| `SAAS_FREE_DAILY_UPLOADS` | `20` | Max jobs created per UTC day per **free** user. |

## API

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/register` | No |
| POST | `/api/auth/login` | No |
| GET | `/api/auth/me` | Bearer |
| GET | `/api/jobs/me` | Bearer |
| POST | `/api/analyze-video`, `/api/analyze-image` | Bearer if `SAAS_REQUIRE_AUTH=true` |
| GET | `/api/results/{id}` | Bearer if `SAAS_REQUIRE_AUTH=true` and job is owned |
| GET | `/api/artifacts/{job_id}/{name}` | Bearer **or** `?access_token=` (for `<img>` tags) |

## Frontend

Set `NEXT_PUBLIC_SAAS_REQUIRE_AUTH=true` when the API uses `SAAS_REQUIRE_AUTH=true` so the UI shows login/register and attaches tokens to requests.

## Production checklist

- [ ] Strong `SAAS_JWT_SECRET` (rotate if leaked).
- [ ] HTTPS only.
- [ ] `SAAS_REQUIRE_AUTH=true`.
- [ ] Email verification (not implemented in MVP).
- [ ] Rate limiting (optional `RATE_LIMIT_RPS`).
