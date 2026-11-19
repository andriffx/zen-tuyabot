"""The dashboard has one account; managing web users is gone."""


def test_web_users_endpoint_is_gone(client, login_as):
    login_as("superadmin")
    assert client.get("/api/web-users").status_code == 404


def test_creating_a_web_user_is_gone(client, csrf_value, login_as):
    login_as("superadmin")
    response = client.post(
        "/api/web-users",
        json={"username": "x", "password": "password-panjang", "role_id": 1},
        headers={"X-CSRF-Token": csrf_value},
    )
    assert response.status_code == 404
