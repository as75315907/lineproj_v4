from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_admin_dashboard() -> None:
    client = TestClient(app)
    response = client.get("/admin/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert "signups" in data


def test_line_webhook_can_persist() -> None:
    client = TestClient(app)
    payload = {
        "events": [
            {
                "type": "postback",
                "replyToken": "dummy-reply-token",
                "timestamp": 1775613600000,
                "webhookEventId": "test-webhook-001",
                "source": {"type": "group", "userId": "U_TEST_001", "groupId": "C_TEST_001"},
                "postback": {"data": "shift=晚10"},
            }
        ]
    }
    response = client.post("/webhook/line", json=payload)
    assert response.status_code == 200
    dashboard = client.get("/admin/api/dashboard?date=2026-04-09").json()
    assert any(r["uid"] == "U_TEST_001" for r in dashboard["signups"])
