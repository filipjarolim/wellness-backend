import pytest
import asyncio
from datetime import datetime, timedelta
from app.services.db_service import db_service
import random

# Real Integration Test with Supabase
@pytest.mark.asyncio
async def test_db_crud_cycle():
    # Force reset DB client to avoid event loop mismatch if other tests ran before
    db_service._client = None
    
    # 1. Setup Data
    test_phone = f"+420999{random.randint(100000, 999999)}" # Unique phone
    test_name = "TEST_QA_USER"
    
    # 2. Create Client
    print(f"Creating client {test_name} with phone {test_phone}")
    client = await db_service.get_or_create_client(test_phone, test_name)
    assert client is not None, "Failed to create client in DB"
    client_id = client.get('id')
    assert client_id is not None
    
    # 3. Create Booking (Log it)
    # Future time
    start_time = datetime.now() + timedelta(days=365) # Next year to avoid messing with current calendar
    service_type = "test_crud"
    gcal_id = f"test_gcal_{random.randint(1000,9999)}"
    
    print(f"Logging booking for client {client_id} at {start_time}")
    await db_service.log_booking(client_id, start_time, service_type, gcal_id)
    
    # 4. Read Booking (Get Upcoming)
    booking = await db_service.get_upcoming_booking_by_client_id(client_id)
    assert booking is not None, "Failed to retrieve the created booking"
    assert booking['service_type'] == service_type
    # Compare timestamps (careful with timezone string vs datetime object)
    # Supabase returns ISO string usually
    saved_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
    # Just check date part or rough equality if needed, but ISO should strictly match if stored correctly
    
    # 5. Check Availability (Manual Simulation via DB)
    # Since we don't have is_slot_busy in db_service, we verified presence via get_upcoming_booking
    
    # 6. Delete Booking
    booking_id = booking['id']
    print(f"Deleting booking {booking_id}")
    success = await db_service.delete_booking(booking_id)
    assert success is True, "Failed to delete booking"
    
    # 7. Verify Deletion
    booking_deleted = await db_service.get_upcoming_booking_by_client_id(client_id)
    assert booking_deleted is None, "Booking should be gone after deletion"

