from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine
from app.routes_auth import router as auth_router
from app.routes_library import router as library_router

app = FastAPI(title=settings.app_name, debug=settings.app_debug)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    _run_compat_migrations()


def _run_compat_migrations():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_admin" not in user_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(library_router)
