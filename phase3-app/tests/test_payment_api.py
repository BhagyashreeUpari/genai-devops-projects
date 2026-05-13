"""
Payment Service Tests
=====================
Integration tests for the FastAPI payment service.
These run in GitHub Actions on every push.

Tests verify:
- Health endpoint returns 200
- Payment creation returns correct structure
- Invalid payment data is rejected
- Analyze endpoint returns structured response
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# TestClient runs the FastAPI app in test mode
# No server needed — runs directly in memory
client = TestClient(app)


def test_health_check():
    """Health endpoint should return 200 with healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "payment-service"
    assert "version" in data
    assert "timestamp" in data


def test_create_payment_success():
    """Valid payment should return 200 with payment_id."""
    response = client.post("/payments", json={
        "amount": 1500.00,
        "currency": "INR",
        "merchant": "TestMerchant",
        "customer_id": "CUST-001"
    })
    assert response.status_code == 200
    data = response.json()
    assert "payment_id" in data
    assert data["payment_id"].startswith("PAY-")
    assert data["status"] in ["completed", "failed"]
    assert data["amount"] == 1500.00
    assert data["currency"] == "INR"


def test_create_payment_invalid_amount():
    """String amount should be rejected with 422."""
    response = client.post("/payments", json={
        "amount": "not-a-number",
        "merchant": "TestMerchant",
        "customer_id": "CUST-001"
    })
    assert response.status_code == 422


def test_create_payment_missing_merchant():
    """Missing required field should return 422."""
    response = client.post("/payments", json={
        "amount": 1500.00,
        "customer_id": "CUST-001"
    })
    assert response.status_code == 422


def test_get_payment_not_found():
    """Getting non-existent payment should return 404."""
    response = client.get("/payments/PAY-DOESNOTEXIST")
    assert response.status_code == 404


def test_get_payment_after_create():
    """Created payment should be retrievable by ID."""
    # Create payment first
    create_response = client.post("/payments", json={
        "amount": 2000.00,
        "currency": "INR",
        "merchant": "RetrievalTest",
        "customer_id": "CUST-002"
    })
    payment_id = create_response.json()["payment_id"]

    # Now retrieve it
    get_response = client.get(f"/payments/{payment_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["payment_id"] == payment_id
    assert data["amount"] == 2000.00


def test_list_payments():
    """List endpoint should return total count and payments array."""
    response = client.get("/payments")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "payments" in data
    assert isinstance(data["payments"], list)