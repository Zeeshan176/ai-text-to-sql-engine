from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_guardrail_rejects_delete():
    from app.guardrails import SQLGuardrail
    is_safe, msg = SQLGuardrail.is_safe_query("DELETE FROM users")
    assert is_safe is False


def test_guardrail_allows_select():
    from app.guardrails import SQLGuardrail
    is_safe, msg = SQLGuardrail.is_safe_query("SELECT * FROM users")
    assert is_safe is True