from datetime import datetime, timezone
from itertools import count

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="uptime-monitor-api", version="0.1.0")


class TargetIn(BaseModel):
    """What a client sends to register a target."""

    url: HttpUrl


class Target(BaseModel):
    """What the API stores and returns."""

    id: int
    url: HttpUrl
    created_at: datetime


# In-memory storage: lost on every restart. Replaced by PostgreSQL in milestone 2.
targets: dict[int, Target] = {}
ids = count(start=1)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: the process is up and answering requests."""
    return {"status": "ok"}


@app.get("/targets")
def list_targets() -> list[Target]:
    """List all monitored targets."""
    return list(targets.values())


@app.post("/targets", status_code=status.HTTP_201_CREATED)
def create_target(target_in: TargetIn) -> Target:
    """Register a new URL to monitor."""
    if any(t.url == target_in.url for t in targets.values()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Target already exists")
    target = Target(id=next(ids), url=target_in.url, created_at=datetime.now(timezone.utc))
    targets[target.id] = target
    return target


@app.get("/targets/{target_id}")
def get_target(target_id: int) -> Target:
    """Get one target by its id."""
    if target_id not in targets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return targets[target_id]


@app.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int) -> None:
    """Stop monitoring a target."""
    if target_id not in targets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    del targets[target_id]
