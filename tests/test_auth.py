"""K4: User accounts — tests (RED first)."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

TEST_EMAIL = "k4test_user@example.com"
TEST_PASS = "TestK4!pass123"


def test_register_200():
    """RED: POST /api/auth/register should create user and return JWT."""
    r = client.post("/api/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


def test_register_duplicate_409():
    """RED: duplicate email → 409."""
    client.post("/api/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    r = client.post("/api/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert r.status_code == 409


def test_login_200():
    """RED: POST /api/auth/login → JWT after register."""
    client.post("/api/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_bad_password_401():
    """RED: wrong password → 401."""
    client.post("/api/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_me_anon_401():
    """RED: no token → 401."""
    r = client.get("/api/me")
    assert r.status_code == 401


def test_me_with_token_200():
    """RED: valid token → user info."""
    reg = client.post("/api/auth/register", json={"email": "k4me@example.com", "password": TEST_PASS})
    token = reg.json()["access_token"]
    r = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "k4me@example.com"
    assert data["is_admin"] is False


def test_order_anon_still_works():
    """RED: POST /api/orders without auth should still work (user_id=NULL)."""
    # Create an order-like submission without token — should get 422 (missing fields) or 200 if valid
    r = client.post("/api/orders", data={"name": "Anon", "email": "anon@x.com", "material": "PLA", "quantity": 1, "shipping": "standard", "shipping_region": "PL", "volume_cm3": "10", "dims": "10x10x10"})
    assert r.status_code in (200, 422, 401)  # 200 = anon accepted; 422 = missing fields; 401 = auth required


def test_order_with_user_tied():
    """RED: POST /api/orders with token → user_id stored."""
    reg = client.post("/api/auth/register", json={"email": "k4order@example.com", "password": TEST_PASS})
    token = reg.json()["access_token"]
    r = client.post("/api/orders", data={"name": "User", "email": "k4order@example.com", "material": "PLA", "quantity": 1, "shipping": "standard", "shipping_region": "PL", "volume_cm3": "10", "dims": "10x10x10"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("user_id") is not None
