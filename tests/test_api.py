"""
API endpoint tests for FastAPI backend.
Validates health check, sample endpoint, input validation, and file upload error handling.
"""

from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify GET / returns healthy status and system capabilities."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["problem_statement"] == "PS-2 (Software Engineering & Development)"
    assert len(data["available_agents"]) == 4
    assert len(data["active_tools"]) == 3


def test_sample_requirements_endpoint():
    """Verify GET /api/sample returns pre-loaded sample requirements text."""
    response = client.get("/api/sample")
    assert response.status_code == 200
    data = response.json()
    assert "SmartClinic" in data["title"]
    assert len(data["text"]) > 100


def test_text_analysis_short_text_rejection():
    """Verify POST /api/analyze-text rejects trivially short text (< 10 chars)."""
    response = client.post("/api/analyze-text", json={"text": "Short"})
    assert response.status_code in (400, 422)



def test_file_analysis_unsupported_extension():
    """Verify POST /api/analyze-file rejects unsupported file extensions."""
    response = client.post(
        "/api/analyze-file",
        files={"file": ("malicious.exe", b"binarycontent", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
