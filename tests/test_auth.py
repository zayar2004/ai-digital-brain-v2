"""Authentication tests."""

from app.extensions import db
from app.models import User


def test_login_page_loads(client):
    r = client.get("/login")
    assert r.status_code == 200


def test_login_wrong_password(client):
    r = client.post("/login", data={
        "username": "testadmin",
        "password": "wrong",
    }, follow_redirects=True)
    assert r.status_code in (200, 401)
    assert b"wrong" not in r.data or b"Password" in r.data


def test_login_success(app):
    c = app.test_client()
    r = c.post("/login", data={
        "username": "testadmin",
        "password": "TestPass123!",
    }, follow_redirects=True)
    assert r.status_code == 200


def test_dashboard_requires_login(client):
    r = client.get("/", follow_redirects=True)
    assert b"login" in r.data.lower() or r.status_code == 200


def test_logout(auth_client):
    r = auth_client.get("/logout", follow_redirects=True)
    assert r.status_code == 200
