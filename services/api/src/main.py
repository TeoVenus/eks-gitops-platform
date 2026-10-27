import os
from contextlib import asynccontextmanager
from datetime import datetime

import psycopg
from fastapi import FastAPI, HTTPException, status
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, HttpUrl

from src.db import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before yield) and once at shutdown (after yield)."""
    app.state.pool = create_pool(os.environ["DATABASE_URL"])
    yield
    app.state.pool.close()


app = FastAPI(title="uptime-monitor-api", version="0.2.0", lifespan=lifespan)


class TargetIn(BaseModel):
    """What a client sends to register a target."""

    url: HttpUrl


class Target(BaseModel):
    """What the API stores and returns."""

    id: int
    url: HttpUrl
    created_at: datetime


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: the process is up and answering requests."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness check: the API can reach the database and can serve traffic."""
    try:
        with app.state.pool.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return {"status": "ready"}


@app.get("/targets")
def list_targets() -> list[Target]:
    """List all monitored targets."""
    with app.state.pool.connection() as conn:
        rows = conn.execute("SELECT id, url, created_at FROM targets ORDER BY id").fetchall()
    return [Target(**row) for row in rows]


@app.post("/targets", status_code=status.HTTP_201_CREATED)
def create_target(target_in: TargetIn) -> Target:
    """Register a new URL to monitor."""
    try:
        with app.state.pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO targets (url) VALUES (%s) RETURNING id, url, created_at",
                (str(target_in.url),),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Target already exists")
    return Target(**row)


@app.get("/targets/{target_id}")
def get_target(target_id: int) -> Target:
    """Get one target by its id."""
    with app.state.pool.connection() as conn:
        row = conn.execute("SELECT id, url, created_at FROM targets WHERE id = %s", (target_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return Target(**row)


@app.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int) -> None:
    """Stop monitoring a target."""
    with app.state.pool.connection() as conn:
        deleted = conn.execute("DELETE FROM targets WHERE id = %s", (target_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
