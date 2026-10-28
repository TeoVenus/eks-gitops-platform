import os
from contextlib import asynccontextmanager
from datetime import datetime

import psycopg
from fastapi import FastAPI, HTTPException, Query, status
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, HttpUrl

from src.db import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before yield) and once at shutdown (after yield)."""
    app.state.pool = create_pool(os.environ["DATABASE_URL"])
    yield
    app.state.pool.close()


app = FastAPI(title="uptime-monitor-api", version="0.3.0", lifespan=lifespan)


class TargetIn(BaseModel):
    """What a client sends to register a target."""

    url: HttpUrl


class Target(BaseModel):
    """What the API stores and returns."""

    id: int
    url: HttpUrl
    created_at: datetime


class CheckResult(BaseModel):
    """One check of a target, as recorded by the checker."""

    checked_at: datetime
    up: bool
    status_code: int | None
    response_ms: int | None
    error: str | None


class TargetStatus(BaseModel):
    """A target with its latest check. The check fields are empty until the first check."""

    id: int
    url: HttpUrl
    up: bool | None
    status_code: int | None
    response_ms: int | None
    error: str | None
    checked_at: datetime | None


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


@app.get("/status")
def get_status() -> list[TargetStatus]:
    """Every target with the result of its latest check."""
    with app.state.pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.url, r.up, r.status_code, r.response_ms, r.error, r.checked_at
            FROM targets t
            LEFT JOIN LATERAL (
                SELECT up, status_code, response_ms, error, checked_at
                FROM check_results
                WHERE target_id = t.id
                ORDER BY checked_at DESC
                LIMIT 1
            ) r ON true
            ORDER BY t.id
            """
        ).fetchall()
    return [TargetStatus(**row) for row in rows]


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


@app.get("/targets/{target_id}/results")
def get_results(target_id: int, limit: int = Query(default=20, ge=1, le=100)) -> list[CheckResult]:
    """The latest check results of one target, newest first."""
    with app.state.pool.connection() as conn:
        if conn.execute("SELECT 1 FROM targets WHERE id = %s", (target_id,)).fetchone() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        rows = conn.execute(
            "SELECT checked_at, up, status_code, response_ms, error FROM check_results"
            " WHERE target_id = %s ORDER BY checked_at DESC LIMIT %s",
            (target_id, limit),
        ).fetchall()
    return [CheckResult(**row) for row in rows]


@app.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int) -> None:
    """Stop monitoring a target."""
    with app.state.pool.connection() as conn:
        deleted = conn.execute("DELETE FROM targets WHERE id = %s", (target_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
