import pytest
from fastapi.testclient import TestClient
from src.server import create_app

app = create_app()
client = TestClient(app)

def test_api_runs_sse_endpoint_exists():
    """Test that the /api/runs/{run_id}/sse endpoint exists and returns SSE."""
    # It should not return 404
    response = client.get("/api/runs/test-run-123/sse")
    # Even if it's a dummy run_id, the endpoint should exist.
    # The actual behavior depends on SSE implementation, but it shouldn't be 404.
    assert response.status_code != 404
    assert response.headers.get("content-type") == "text/event-stream; charset=utf-8"

def test_api_sse_exports_endpoint_exists():
    """Test that the /api/sse/exports endpoint exists and returns SSE."""
    # It requires user_id
    response = client.get("/api/sse/exports?user_id=test-user-123")
    assert response.status_code != 404
    assert response.headers.get("content-type") == "text/event-stream; charset=utf-8"
