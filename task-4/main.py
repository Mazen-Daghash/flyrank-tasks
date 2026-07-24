from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import get_current_user, supabase

app = FastAPI(
    title="Auth API",
    description="Sign up, log in, log out, and guard routes with Supabase-issued JWTs.",
    version="1.0",
)


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
def profile(user=Depends(get_current_user)):
    """Requires a valid Bearer token, verified by the get_current_user guard."""
    return {"id": user.id, "email": user.email, "created_at": user.created_at}


@app.get("/protected/dashboard")
def dashboard(user=Depends(get_current_user)):
    """Second protected route, reusing the exact same guard - no new auth code."""
    return {"message": f"Welcome back, {user.email}!"}


@app.post("/auth/logout", status_code=204)
def logout(user=Depends(get_current_user)):
    """Protected: ends the current session via Supabase."""
    supabase.auth.sign_out()
    return None
