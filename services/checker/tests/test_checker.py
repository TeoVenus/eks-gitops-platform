import httpx2

from src.main import check


def client_returning(handler) -> httpx2.Client:
    """An HTTP client that never touches the network: `handler` answers every request."""
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_site_answering_200_is_up():
    client = client_returning(lambda request: httpx2.Response(200))

    result = check(client, "https://example.com")

    assert result["up"] is True
    assert result["status_code"] == 200
    assert result["response_ms"] >= 0
    assert result["error"] is None


def test_site_answering_500_is_down():
    client = client_returning(lambda request: httpx2.Response(500))

    result = check(client, "https://example.com")

    assert result["up"] is False
    assert result["status_code"] == 500


def test_unreachable_site_is_down_with_error():
    def fail(request):
        raise httpx2.ConnectError("connection refused")

    result = check(client_returning(fail), "https://example.com")

    assert result == {"up": False, "status_code": None, "response_ms": None, "error": "ConnectError"}
