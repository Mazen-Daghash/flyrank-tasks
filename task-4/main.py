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
