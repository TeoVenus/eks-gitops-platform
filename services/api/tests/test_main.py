import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def database():
    """Run the app's startup once for all tests: opens the pool and creates the table."""
    with client:
        yield


@pytest.fixture(autouse=True)
def empty_storage(database):
    """Start every test with an empty table, so tests can't affect each other."""
    with app.state.pool.connection() as conn:
        conn.execute("TRUNCATE targets RESTART IDENTITY CASCADE")


def add_result(target_id, up, status_code, minutes_ago):
    """Store a check result directly in the database, the way the checker would."""
    with app.state.pool.connection() as conn:
        conn.execute(
            "INSERT INTO check_results (target_id, up, status_code, response_ms, checked_at)"
            " VALUES (%s, %s, %s, 100, now() - make_interval(mins => %s))",
            (target_id, up, status_code, minutes_ago),
        )


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_is_reachable():
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_create_target_returns_201_and_the_target():
    response = client.post("/targets", json={"url": "https://example.com"})

    assert response.status_code == 201
    body = response.json()
    assert body["url"] == "https://example.com/"
    assert "id" in body
    assert "created_at" in body


def test_created_target_can_be_fetched_and_listed():
    created = client.post("/targets", json={"url": "https://example.com"}).json()

    assert client.get(f"/targets/{created['id']}").json() == created
    assert client.get("/targets").json() == [created]


def test_duplicate_target_returns_409():
    client.post("/targets", json={"url": "https://example.com"})

    response = client.post("/targets", json={"url": "https://example.com/"})

    assert response.status_code == 409


def test_invalid_url_returns_422():
    response = client.post("/targets", json={"url": "not-a-url"})

    assert response.status_code == 422


def test_unknown_target_returns_404():
    response = client.get("/targets/999")

    assert response.status_code == 404


def test_delete_target_removes_it():
    created = client.post("/targets", json={"url": "https://example.com"}).json()

    assert client.delete(f"/targets/{created['id']}").status_code == 204
    assert client.get(f"/targets/{created['id']}").status_code == 404


def test_multiple_targets_can_be_registered():
    urls = ["https://example.com", "https://example.org", "https://www.python.org"]

    for url in urls:
        assert client.post("/targets", json={"url": url}).status_code == 201

    assert len(client.get("/targets").json()) == 3


def test_status_of_unchecked_target_is_empty():
    created = client.post("/targets", json={"url": "https://example.com"}).json()

    [entry] = client.get("/status").json()

    assert entry["id"] == created["id"]
    assert entry["up"] is None
    assert entry["checked_at"] is None


def test_status_shows_latest_result():
    target = client.post("/targets", json={"url": "https://example.com"}).json()
    add_result(target["id"], up=True, status_code=200, minutes_ago=5)
    add_result(target["id"], up=False, status_code=503, minutes_ago=1)

    [entry] = client.get("/status").json()

    assert entry["up"] is False
    assert entry["status_code"] == 503


def test_results_are_newest_first_and_limited():
    target = client.post("/targets", json={"url": "https://example.com"}).json()
    add_result(target["id"], up=False, status_code=500, minutes_ago=3)
    add_result(target["id"], up=True, status_code=200, minutes_ago=1)
    add_result(target["id"], up=False, status_code=503, minutes_ago=2)

    results = client.get(f"/targets/{target['id']}/results?limit=2").json()

    assert [r["status_code"] for r in results] == [200, 503]


def test_results_of_unknown_target_returns_404():
    response = client.get("/targets/999/results")

    assert response.status_code == 404
