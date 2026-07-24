from fastapi import FastAPI

from auth import supabase

app = FastAPI()


@app.on_event("startup")
def on_startup():
    print("Server running and connected to Supabase")
