def test_list_returns_every_key_with_placeholders(client, login_as):
    login_as("superadmin")
    body = client.get("/api/bot-messages").json()

    by_key = {item["key"]: item for item in body["messages"]}
    assert "deny.rate_limit" in by_key
    assert "action" in by_key["deny.role"]["placeholders"]


def test_put_rejects_blank_text(client, csrf_value, login_as):
    login_as("superadmin")
    response = client.put(
        "/api/bot-messages/deny.role",
        json={"text": "   "},
        headers={"X-CSRF-Token": csrf_value},
    )
    assert response.status_code == 422


def test_put_saves_and_reads_back(client, csrf_value, login_as):
    login_as("superadmin")
    response = client.put(
        "/api/bot-messages/deny.role",
        json={"text": "Butuh {action} dulu."},
        headers={"X-CSRF-Token": csrf_value},
    )
    assert response.status_code == 200

    body = client.get("/api/bot-messages").json()
    stored = next(item for item in body["messages"] if item["key"] == "deny.role")
    assert stored["text"] == "Butuh {action} dulu."


def test_put_refuses_an_unknown_key(client, csrf_value, login_as):
    login_as("superadmin")
    response = client.put(
        "/api/bot-messages/tidak.ada",
        json={"text": "x"},
        headers={"X-CSRF-Token": csrf_value},
    )
    assert response.status_code == 404


def test_preview_fills_known_placeholders(client, login_as):
    login_as("superadmin")
    body = client.post("/api/bot-messages/deny.role/preview").json()
    assert "{action}" not in body["text"]
    assert "menyalakan" in body["text"]


def test_preview_works_for_a_formatted_placeholder(client, login_as):
    """notify.watchdog_off_idle uses {power:.1f}; a string sample 500s on it."""
    login_as("superadmin")
    response = client.post("/api/bot-messages/notify.watchdog_off_idle/preview")

    assert response.status_code == 200
    assert "12.5" in response.json()["text"]
