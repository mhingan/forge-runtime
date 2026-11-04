from fastapi.testclient import TestClient

from forge_runtime import api


def test_health_endpoint() -> None:
    client = TestClient(api.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "forge-runtime"


def test_registry_endpoints_use_installed_agentforge_toolkit() -> None:
    client = TestClient(api.app)
    agents = client.get("/v1/agents")
    skills = client.get("/v1/skills")

    assert agents.status_code == 200
    assert skills.status_code == 200
    assert any(item["name"] == "architect" for item in agents.json())
    assert any(item["name"] == "architecture" for item in skills.json())


def test_create_mock_run_end_to_end(tmp_path) -> None:
    api.settings.database_url = f"sqlite:///{tmp_path / 'api.db'}"
    client = TestClient(api.app)

    response = client.post(
        "/v1/runs",
        json={"goal": "Design a small inventory API", "provider": "mock"},
    )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert len(run["plan"]["tasks"]) == 3
    assert run["summary"].startswith("All 3 task(s) succeeded")
