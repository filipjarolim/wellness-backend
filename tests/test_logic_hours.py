import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch
from app.services.booking_service import BookingService

# Helper to run async tests
@pytest.mark.asyncio
async def test_opening_hours_logic():
    # Mock external dependencies to isolate logic
    with patch("app.services.booking_service.check_calendar_availability", new_callable=AsyncMock) as mock_cal:
        # Default: Calendar says FREE (so we only test Business Hours logic)
        mock_cal.return_value = True 

        service = BookingService()

        # 1. Sunday -> CLOSED (Based on company_config.json: "sunday": null)
        # 2023-12-31 is a Sunday
        res = await service.check_availability("2023-12-31", "12:00")
        assert "zavřeno" in res.lower() or "neděli" in res.lower(), f"Sunday should be closed. Got: {res}"

        # 2. Tuesday 03:00 -> CLOSED (Outside 09:00 - 18:00)
        # 2024-01-02 is a Tuesday
        res = await service.check_availability("2024-01-02", "03:00")
        assert "máme otevřeno jen od" in res.lower() or "zavřeno" in res.lower(), f"Tuesday 03:00 should be closed. Got: {res}"

        # 3. Monday 14:00 -> OPEN
        # 2024-01-01 is a Monday
        res = await service.check_availability("2024-01-01", "14:00")
        assert "mám volno" in res.lower(), f"Monday 14:00 should be open. Got: {res}"
