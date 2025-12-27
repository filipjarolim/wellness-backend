from typing import Optional
from sqlmodel import Session, select
from app.models.db_models import Booking

class BookingService:
    def __init__(self, session: Session):
        self.session = session

    def check_availability(self, day: str, time: Optional[str] = None) -> str:
        """
        Check availability for a given day and optionally a time from the DB.
        """
        if not time:
            return f"Checking generic availability for {day} is not fully implemented yet."

        # Check in DB if there is a booking for this day and time
        # Note: In a real app, normalize day/time formats carefully.
        statement = select(Booking).where(Booking.day == day, Booking.time == time)
        results = self.session.exec(statement)
        existing_booking = results.first()
        
        if existing_booking:
            return f"Sorry, {day} at {time} is fully booked."
        
        return f"Yes, {day} at {time} is available."

    def book_appointment(self, day: str, time: str, name: str, service: str = "general") -> dict:
        """
        Book an appointment and save to DB.
        """
        if not day or not time or not name:
            return {"result": "error", "message": "Missing details for booking."}

        # Double check availability/existence before insert to avoid duplicates (optional but good practice)
        availability_msg = self.check_availability(day, time)
        if "fully booked" in availability_msg:
             return {"result": "error", "message": f"Time slot {day} {time} is already booked."}

        # Create DB record
        booking = Booking(name=name, day=day, time=time, service=service)
        self.session.add(booking)
        self.session.commit()
        self.session.refresh(booking)
        
        print(f"✅ NOVÁ REZERVACE (DB): {name} na {day} v {time} - {service} (ID: {booking.id})")
        
        return {"result": "success", "message": "Termín je úspěšně rezervován."}
