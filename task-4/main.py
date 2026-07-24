from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import supabase

app = FastAPI()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.on_event("startup")
def on_startup():
    print("Server running and connected to Supabase")


class Credentials(BaseModel):
    email: str | None = None
    password: str | None = None


@app.post("/auth/signup", status_code=201)
def signup(creds: Credentials):
    """Register a new user with Supabase. Returns 400 if email/password is missing."""
    if not creds.email or not creds.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    try:
        result = supabase.auth.sign_up({"email": creds.email, "password": creds.password})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.user


@app.post("/auth/login")
def login(creds: Credentials):
    """Log in via Supabase. Returns 401 on bad credentials, 200 with tokens on success."""
    if not creds.email or not creds.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": creds.email, "password": creds.password}
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid login credentials")
    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
    }


@app.get("/public/info")
def public_info():
    """Open endpoint, no auth required."""
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile")
def profile(request: Request):
    """Requires a Bearer token, verified against Supabase on every request."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer ") or len(auth_header) <= len("Bearer "):
        raise HTTPException(status_code=401, detail="Access token required")
    token = auth_header.removeprefix("Bearer ")

    try:
        response = supabase.auth.get_user(token)
    except Exception:
        response = None
    if response is None or response.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = response.user
    return {"id": user.id, "email": user.email, "created_at": user.created_at}
