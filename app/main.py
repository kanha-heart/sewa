from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from .config import DEV_MODE
from .db import engine, init_db
from .routers import admin, auth, public
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if DEV_MODE:
        with Session(engine) as session:
            seed_if_empty(session)
    yield


app = FastAPI(title="Sewa", lifespan=lifespan)


@app.get("/api/ping")
def ping():
    return {"ok": True}


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(admin.router)

# The screens (HTML, CSS, JS) live in the static folder. This must come last.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
