from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.services.booking_service import BookingService
from datetime import datetime

router = APIRouter()
booking_service = BookingService()

class CheckAvailabilityRequest(BaseModel):
    day: str
    time: str

class BookAppointmentRequest(BaseModel):
    day: str
    time: str
    name: str
    phone: str
    service: Optional[str] = "general"

class GetBookingRequest(BaseModel):
    phone: str

class CancelBookingRequest(BaseModel):
    phone: str

@router.post("/tools/check_availability")
async def check_availability(req: CheckAvailabilityRequest):
    result = await booking_service.check_availability(req.day, req.time)
    return {"result": result}

@router.post("/tools/book_appointment")
async def book_appointment(req: BookAppointmentRequest, background_tasks: BackgroundTasks):
    result = await booking_service.book_appointment(
        req.day, req.time, req.name, req.phone, req.service, background_tasks
    )
    return {"message": result}

@router.post("/tools/get_booking")
async def get_booking(req: GetBookingRequest):
    # Normalize phone
    phone = req.phone.replace(" ", "").strip()
    
    booking = await booking_service.get_active_booking(phone)
    
    if booking:
        # Parse ISO date to separate date/time
        try:
            dt = datetime.fromisoformat(booking['start_time'].replace("Z", "+00:00"))
            return {
                "exists": True,
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"),
                "service": booking.get("service_type")
            }
        except Exception:
            # Fallback if parsing fails
            return {
                "exists": True, 
                "raw_date": booking.get('start_time'), 
                "service": booking.get("service_type")
            }
    else:
        return {"exists": False}

@router.post("/tools/cancel_booking")
async def cancel_booking(req: CancelBookingRequest, background_tasks: BackgroundTasks):
    # Normalize phone
    phone = req.phone.replace(" ", "").strip()
    
    # We use cancel_booking which returns a string message, but requirement asks for success bool + message
    # Let's peek at cancel_booking implementation: it returns a message string.
    # To conform to JSON requirement { "success": true, "message": "..." }, we might need to interpret the message
    # OR we can call cancel_active_booking directly and construct the message ourselves.
    # The requirement says: logic Calls `booking_service.cancel_booking(phone)`.
    # But `booking_service.cancel_booking` returns a human readable string. 
    # Let's call `cancel_booking` (the Vapi wrapper) to reuse notification logic, 
    # and then wrap the string result in the JSON structure.
    
    msg = await booking_service.cancel_booking(phone, background_tasks)
    
    # Heuristic to determine success boolean from message
    is_success = "byla zrušena" in msg
    
    return {
        "success": is_success,
        "message": msg
    }
