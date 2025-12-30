import asyncio
import os
import random
import string
from datetime import datetime, timedelta
import logging

# Configure logger early
from app.core.logger import logger

# Mock external services to avoid spam/API calls
import app.services.booking_service
import app.services.calendar_service

async def mock_send_notification(*args, **kwargs):
    print("      📧 [MOCK] Sending Notification (Skipped)")

# Change to Sync Mock
def mock_send_notification_sync(*args, **kwargs):
    print("      📧 [MOCK] Sending Notification (Sync/Blocking) (Skipped)")

async def mock_check_calendar(*args, **kwargs):
    print("      📅 [MOCK] Checking Calendar (Skipped - Always Available)")
    return True

async def mock_create_event(*args, **kwargs):
    print("      📅 [MOCK] Creating Calendar Event (Skipped)")
    return {'id': 'mock_gcal_id', 'htmlLink': 'http://mock'}

# Apply Mocks
# IMPORTANT: We must patch the namespace where they are USED (booking_service), 
# because they were imported via 'from ... import ...'
app.services.booking_service.send_sms = mock_send_notification_sync
app.services.booking_service.send_email = mock_send_notification_sync
app.services.booking_service.check_calendar_availability = mock_check_calendar
app.services.booking_service.create_calendar_event = mock_create_event

from app.services.booking_service import BookingService

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'
CYAN = '\033[96m'

def generate_phone():
    return "+420" + "".join(random.choices(string.digits, k=9))

def generate_name():
    return "Test User " + "".join(random.choices(string.ascii_uppercase, k=3))

async def run_test():
    print(f"\n{CYAN}🚀 STARTING SUPABASE FLOW TEST{RESET}")
    
    phone = generate_phone()
    name = generate_name()
    service_type = "Wellness Test"
    
    # Calculate future date (tomorrow 14:00)
    tmr = datetime.now() + timedelta(days=1)
    day_str = tmr.strftime("%Y-%m-%d")
    time_str = "14:00"
    
    bs = BookingService()

    print(f"📋 Test Data: Name={name}, Phone={phone}")

    try:
        # TEST 1: Insert (Book Appointment)
        print(f"\n{CYAN}[1] Testing Create Booking...{RESET}")
        result_msg = await bs.book_appointment(day_str, time_str, name, phone, service_type)
        print(f"    Result: {result_msg}")
        assert "máte rezervováno" in result_msg or "potvrzuji" in result_msg.lower() or "úspěšně vytvořena" in result_msg.lower(), "Booking failed message mismatch"
        print(f"{GREEN}✅ PASS: Create Booking{RESET}")

        # TEST 2: Read (Get Active Booking)
        print(f"\n{CYAN}[2] Testing Get Active Booking...{RESET}")
        booking = await bs.get_active_booking(phone)
        assert booking is not None, "Booking not found in DB"
        assert booking['service_type'] == service_type, f"Service mismatch: {booking.get('service_type')}"
        print(f"    Found ID: {booking['id']}, Time: {booking['start_time']}")
        print(f"{GREEN}✅ PASS: Get Active Booking{RESET}")

        # TEST 3: Duplicate Check (Get Active Booking again)
        print(f"\n{CYAN}[3] Testing Duplicate Check...{RESET}")
        booking2 = await bs.get_active_booking(phone)
        assert booking2['id'] == booking['id'], "IDs do not match"
        print(f"{GREEN}✅ PASS: Duplicate Check{RESET}")

        # TEST 4: Cancel
        print(f"\n{CYAN}[4] Testing Cancel Booking...{RESET}")
        was_cancelled = await bs.cancel_active_booking(phone)
        assert was_cancelled is True, "Cancel returned False"
        print(f"{GREEN}✅ PASS: Cancel Booking{RESET}")

        # TEST 5: Verify Cancel
        print(f"\n{CYAN}[5] Verify Cancellation...{RESET}")
        booking3 = await bs.get_active_booking(phone)
        assert booking3 is None, "Booking still exists after cancellation!"
        print(f"{GREEN}✅ PASS: Verify Cancel{RESET}")

        print(f"\n{GREEN}✅✅✅ VŠECHNY DB TESTY PROŠLY ✅✅✅{RESET}\n")

    except AssertionError as e:
        print(f"\n{RED}❌ TEST FAILED: {e}{RESET}")
    except Exception as e:
        print(f"\n{RED}❌ EXCEPTION: {e}{RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
