import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import AsyncMock, patch

client = TestClient(app)

def test_tool_check_availability():
    # Payload matching what Vapi might send or simple args
    payload = {
        "day": "2024-01-01",
        "time": "14:00"
    }
    response = client.post("/tools/check_availability", json=payload)
    
    # We expect the endpoint to exist
    assert response.status_code == 200
    # We expect a JSON string message
    assert "message" in response.json() or "result" in response.json()
    # Check content (assuming logic from BookingService)
    # The actual content depends on logic_hours test, but we just check structural 200 OK here
    # and that it returns SOME string.

def test_tool_book_appointment():
    payload = {
        "day": "2024-01-01",
        "time": "14:00",
        "name": "API Tester",
        "phone": "+420700000000",
        "service": "api_test"
    }
    response = client.post("/tools/book_appointment", json=payload)
    
    assert response.status_code == 200
    # Must contain confirmation or logic message
    json_resp = response.json()
    # It might fail if availability check blocks it, but status code should be 200 (application handled it)
    assert isinstance(json_resp, dict)

def test_tool_get_booking():
    with patch("app.services.booking_service.BookingService.get_active_booking", new_callable=AsyncMock) as mock_get:
        # Case 1: Exists
        mock_get.return_value = {
            "start_time": "2024-01-01T15:00:00",
            "service_type": "haircut"
        }
        
        response = client.post("/tools/get_booking", json={"phone": "+420 777 000 000"})
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["date"] == "2024-01-01"
        assert data["time"] == "15:00"
        
        # Case 2: Not found
        mock_get.return_value = None
        response = client.post("/tools/get_booking", json={"phone": "+420111"})
        assert response.status_code == 200
        assert response.json()["exists"] is False

def test_tool_cancel_booking():
    # We mock cancel_booking wrapper from BookingService
    with patch("app.services.booking_service.BookingService.cancel_booking", new_callable=AsyncMock) as mock_cancel:
        mock_cancel.return_value = "Vaše rezervace na 01.01. 15:00 byla zrušena."
        
        response = client.post("/tools/cancel_booking", json={"phone": "+420 777 000 000"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "byla zrušena" in data["message"]

