import logging
import os
import signal
import threading
import time

import httpx2
import psycopg
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import dict_row

CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "30"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "5"))

log = logging.getLogger("checker")

# Set when the container is asked to stop (SIGTERM from Docker or Kubernetes).
stop = threading.Event()


def check(client: httpx2.Client, url: str) -> dict:
    """Request a URL once and report whether it is up and how fast it answered."""
    start = time.perf_counter()
    try:
        response = client.get(url)
    except httpx2.HTTPError as exc:  # timeout, DNS failure, connection refused, ...
        return {"up": False, "status_code": None, "response_ms": None, "error": type(exc).__name__}
    response_ms = round((time.perf_counter() - start) * 1000)
    return {"up": response.status_code < 400, "status_code": response.status_code, "response_ms": response_ms, "error": None}


def run_once(conn: psycopg.Connection, client: httpx2.Client) -> int:
    """Check every target once and store the results. Returns how many were checked."""
    targets = conn.execute("SELECT id, url FROM targets ORDER BY id").fetchall()
    for target in targets:
        result = check(client, target["url"])
        try:
            conn.execute(
                "INSERT INTO check_results (target_id, up, status_code, response_ms, error)"
                " VALUES (%(target_id)s, %(up)s, %(status_code)s, %(response_ms)s, %(error)s)",
                {"target_id": target["id"], **result},
            )
        except ForeignKeyViolation:
            pass  # the target was deleted while we were checking it
        log.info(
            "%s up=%s status=%s response_ms=%s error=%s",
            target["url"], result["up"], result["status_code"], result["response_ms"], result["error"],
        )
    return len(targets)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # we log each check ourselves
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    database_url = os.environ["DATABASE_URL"]

    log.info("checking every %ss", CHECK_INTERVAL_SECONDS)
    with httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
        while not stop.is_set():
            try:
                # A fresh connection per round: if the database restarts, the next round just reconnects.
                with psycopg.connect(database_url, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
                    checked = run_once(conn, client)
                log.info("round finished: %d targets checked", checked)
            except psycopg.Error as exc:
                log.warning("database not available, retrying next round: %s", exc)
            stop.wait(CHECK_INTERVAL_SECONDS)  # sleeps, but wakes up immediately on SIGTERM
    log.info("stopped")


if __name__ == "__main__":
    main()
