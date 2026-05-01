# Freemium SaaS mode

## Overview

- **Users** table with email + bcrypt password.
- **JWT** access tokens: **`Authorization: Bearer <token>`** and/or **HttpOnly** session cookie (`Set-Cookie` on login/register; name from `SAAS_AUTH_COOKIE_NAME`).
- **Jobs** are linked to `user_id` when authenticated.
- **Free tier**: daily upload cap (`SAAS_FREE_DAILY_UPLOADS`, UTC midnight reset). **`pro`** tier skips the cap (placeholder for billing later).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `SAAS_REQUIRE_AUTH` | `false` | If `true`, all uploads and result/artifact reads require a valid JWT (except health/docs). |
| `SAAS_JWT_SECRET` | dev placeholder | **Must be >= 32 characters and randomly generated in production.** |
| `SAAS_JWT_EXP_HOURS` | `168` | Token lifetime (hours). |
| `SAAS_FREE_DAILY_UPLOADS` | `20` | Max jobs created per UTC day per **free** user. |
| `SAAS_AUTH_COOKIE_*`, `SAAS_RETURN_TOKEN_IN_BODY` | see `.env.example` | Cookie security (`Secure`, `SameSite`) and whether JSON includes `access_token`. |

## API

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/register` | No — sets session cookie; optional `access_token` in body |
| POST | `/api/auth/login` | No — same |
| POST | `/api/auth/logout` | Clears session cookie |
| GET | `/api/auth/me` | Bearer **or** cookie |
| GET | `/api/jobs/me` | Bearer **or** cookie |
| POST | `/api/analyze-video`, `/api/analyze-image` | Bearer if `SAAS_REQUIRE_AUTH=true` |
| GET | `/api/results/{id}` | Bearer if `SAAS_REQUIRE_AUTH=true` and job is owned |
| GET | `/api/artifacts/{job_id}/{name}` | Bearer (required when `SAAS_REQUIRE_AUTH=true`) |

## Frontend

Set `NEXT_PUBLIC_SAAS_REQUIRE_AUTH=true` when the API uses `SAAS_REQUIRE_AUTH=true` so the UI shows login/register. The app sends **`credentials: "include"`** on API fetches so HttpOnly cookies are used; legacy **`localStorage`** tokens still work if `SAAS_RETURN_TOKEN_IN_BODY=true` and the client stores them.

## Production checklist

- [ ] Strong `SAAS_JWT_SECRET` (rotate if leaked).
- [ ] HTTPS only.
- [ ] `SAAS_REQUIRE_AUTH=true`.
- [ ] Email verification (not implemented in MVP).
- [ ] Rate limiting (optional `RATE_LIMIT_RPS`).
