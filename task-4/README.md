# Task 4 — Auth: Login & Protect

FlyRank Backend Track · Week 2 · Assignment A4

A small FastAPI service that hands off identity to **Supabase Auth**: it never stores a
password and never hashes anything itself. Supabase manages accounts and signs JSON Web
Tokens (JWTs); this server's job is to send credentials to Supabase, verify the tokens it
hands back, and use that to guard specific routes.

## Setup

1. Create a free project at [supabase.com](https://supabase.com).
2. In **Project Settings → API**, copy the **Project URL** and the **`anon` `public`** key
   (never the `service_role` key — that bypasses all security).
3. In **Authentication → Providers → Email**, turn **"Confirm email" off** for this practice
   project, so a fresh signup can log in immediately without clicking an email link.
4. Copy `.env.example` to `.env` and fill in your values:

   ```bash
   cp .env.example .env
   ```

   ```
   SUPABASE_URL=your_project_url
   SUPABASE_KEY=your_anon_key
   PORT=8000
   ```

   `.env` is git-ignored and was never committed — only `.env.example` (placeholder values)
   is in the repo.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --port 8000
```

- API root: http://localhost:8000/
- Swagger UI: http://localhost:8000/docs

## API reference

| Method | Path                  | Description                     | Auth required |
|--------|-----------------------|----------------------------------|----------------|
| POST   | `/auth/signup`        | Create a new user account        | No             |
| POST   | `/auth/login`         | Log in, returns access + refresh tokens | No       |
| POST   | `/auth/logout`        | End the current session          | Yes (Bearer)   |
| GET    | `/public/info`        | Open, unauthenticated info       | No             |
| GET    | `/protected/profile`  | Current user's id/email/created_at | Yes (Bearer) |
| GET    | `/protected/dashboard`| Second protected route, same guard | Yes (Bearer) |

All auth errors return `{"error": "..."}` with the matching status code:
- `400` — missing/empty email or password on signup/login
- `401` — wrong login credentials, missing bearer token, or an invalid/expired/tampered token

## How the guard works

`auth.py` defines one dependency, `get_current_user`, built on FastAPI's `HTTPBearer`
security scheme:

1. Pull the token out of the `Authorization: Bearer <token>` header.
2. Missing/empty token → `401 {"error": "Access token required"}`.
3. Otherwise call `supabase.auth.get_user(token)` — a real network call to Supabase, so the
   answer is trustworthy, not just a local signature check.
4. Invalid, expired, or tampered token → `401 {"error": "Invalid or expired token"}`.
5. Valid token → the Supabase user object is injected into the route.

`GET /protected/profile`, `GET /protected/dashboard`, and `POST /auth/logout` all just declare
`user=Depends(get_current_user)` — the guard is written once and reused, so no route can
accidentally forget to check auth.

## Swagger UI

FastAPI auto-generates a bearer-auth padlock from the `HTTPBearer` scheme used by the guard.
Click **Authorize** in `/docs`, paste an `access_token` from `POST /auth/login`, and
**Try it out** on any protected route directly from the browser.

![Swagger UI with Authorize padlock](docs/swagger.png)

## Example flow

```bash
curl -i -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
# -> 201, user object

curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
# -> 200, {"access_token": "...", "refresh_token": "..."}

curl -i http://localhost:8000/protected/profile \
  -H "Authorization: Bearer <PASTE_ACCESS_TOKEN_HERE>"
# -> 200, {"id": "...", "email": "test@example.com", "created_at": "..."}

curl -i http://localhost:8000/protected/profile \
  -H "Authorization: Bearer not-a-real-token"
# -> 401, {"error": "Invalid or expired token"}
```

## Notes

- No password is ever stored or hashed in this codebase — Supabase does all of that.
- The `anon` key is safe to ship in a client-side app; it only lets you do what your
  Supabase Row Level Security policies allow. The `service_role` key is never used here.
