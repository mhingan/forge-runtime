from fastapi.testclient import TestClient

from forge_runtime import api


def test_health_endpoint() -> None:
    client = TestClient(api.app, client=("127.0.0.1", 43123))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "forge-runtime"


def test_registry_endpoints_use_installed_agentforge_toolkit() -> None:
    client = TestClient(api.app, client=("127.0.0.1", 43123))
    agents = client.get("/v1/agents")
    skills = client.get("/v1/skills")

    assert agents.status_code == 200
    assert skills.status_code == 200
    assert any(item["name"] == "architect" for item in agents.json())
    assert any(item["name"] == "architecture" for item in skills.json())


def test_create_mock_run_end_to_end(tmp_path) -> None:
    api.settings.database_url = f"sqlite:///{tmp_path / 'api.db'}"
    client = TestClient(api.app, client=("127.0.0.1", 43123))

    response = client.post(
        "/v1/runs",
        json={"goal": "Design a small inventory API", "provider": "mock"},
    )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert len(run["plan"]["tasks"]) == 3
    assert run["summary"].startswith("All 3 task(s) succeeded")



def test_non_loopback_client_requires_api_token() -> None:
    previous_token = api.settings.api_token
    try:
        api.settings.api_token = None
        client = TestClient(api.app, client=("203.0.113.10", 43123))
        response = client.get("/health")
        assert response.status_code == 401
    finally:
        api.settings.api_token = previous_token


def test_non_loopback_client_can_authenticate_with_api_token() -> None:
    previous_token = api.settings.api_token
    try:
        api.settings.api_token = "test-api-key"
        client = TestClient(api.app, client=("203.0.113.10", 43123))
        response = client.get("/health", headers={"X-Forge-API-Key": "test-api-key"})
        assert response.status_code == 200
    finally:
        api.settings.api_token = previous_token
