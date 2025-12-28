from typing import Optional
from sqlmodel import Session, select
from app.models.db_models import Booking

from datetime import datetime, timedelta
import traceback
import logging
from zoneinfo import ZoneInfo

# Import calendar functions
from app.services.calendar_service import check_calendar_availability, create_calendar_event

logger = logging.getLogger(__name__)

TZ = ZoneInfo('Europe/Prague')

CZECH_MONTHS = {
    1: "ledna", 2: "února", 3: "března", 4: "dubna", 5: "května", 6: "června",
    7: "července", 8: "srpna", 9: "září", 10: "října", 11: "listopadu", 12: "prosince"
}

class BookingService:
    def __init__(self, session: Session):
        self.session = session



    def check_availability(self, day: str, time: Optional[str] = None) -> str:
        """
        Check availability for a given day and optionally a time from the DB and Google Calendar.
        """
        if not time:
            return f"Checking generic availability for {day} is not fully implemented yet."
        
        try:
            start_dt = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        except ValueError as e:
            logger.error(f"Date parsing failed for {day} {time}: {e}")
            return f"Invalid date or time format. Please provide YYYY-MM-DD and HH:MM."

        if start_dt:
             # Check Google Calendar
             is_calendar_free = check_calendar_availability(start_dt)
             if not is_calendar_free:
                 formatted_date = start_dt.strftime("%d.%m. %H:%M")
                 return f"Sorry, {formatted_date} is busy in the calendar."
             
             # Use ISO format for DB check consistency
             db_day = start_dt.strftime("%Y-%m-%d")
             db_time = start_dt.strftime("%H:%M")

        # 2. Check in DB if there is a booking for this day and time
        # Note: We rely on exact string match if parsing failed, or ISO match if succeeded
        statement = select(Booking).where(Booking.day == db_day, Booking.time == db_time)
        results = self.session.exec(statement)
        existing_booking = results.first()
        
        if existing_booking:
            return f"Sorry, {day} at {time} is fully booked."
        
        return f"Yes, {day} at {time} is available."

    def book_appointment(self, day: str, time: str, name: str, service: str = "general") -> str:
        """
        Book an appointment and save to DB.
        Returns a human-readable text response for the AI to read.
        """
        if not day or not time or not name:
             logger.info(f'📥 Booking Request - Day: {day}, Time: {time}')
             return "Omlouvám se, ale chybí mi některé údaje pro vytvoření rezervace."

        logger.info(f'📥 Booking Request - Day: {day}, Time: {time}')

        # Check availability again
        availability_msg = self.check_availability(day, time)
        if "fully booked" in availability_msg or "busy" in availability_msg:
             return "Omlouvám se, ale termín se nepodařilo zarezervovat. Zkuste to prosím znovu."

        # Parse date for storage normalization and Calendar
        try:
            start_dt = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            logger.info(f'📅 Vypočítaný Start Time: {start_dt}')
            
            save_day = start_dt.strftime("%Y-%m-%d")
            save_time = start_dt.strftime("%H:%M")
            logger.info(f"📅 Parsed Date: {start_dt}")
            
        except ValueError as e:
            logger.error(f"Cannot parse booking date: {day} {time} error: {e}")
            return "Omlouvám se, ale termín se nepodařilo zarezervovat. Zkuste to prosím znovu."

        # Create DB record
        booking = Booking(name=name, day=save_day, time=save_time, service=service)
        self.session.add(booking)
        self.session.commit()
        self.session.refresh(booking)
        
        logger.info(f"✅ NOVÁ REZERVACE (DB): {name} na {save_day} v {save_time} - {service} (ID: {booking.id})")
        
        # Sync to Google Calendar
        logger.info('🚀 Calling Google Calendar...')
        try:
            # Pass clean datetime object to calendar service
            html_link = create_calendar_event(booking, start_time=start_dt)
            if html_link:
                 logger.info(f"✅ Synced to Calendar: {html_link}")
        except Exception as e:
            logger.error(f"❌ Google Error: {e}") 
            # We don't want to fail the booking if calendar fails, so we just log.
        
        # Format date for user response: "14. ledna 2026"
        month_name = CZECH_MONTHS.get(start_dt.month, "")
        formatted_day = f"{start_dt.day}. {month_name} {start_dt.year}"
        
        return f"Vaše rezervace na jméno {name} na {formatted_day} v {time} byla úspěšně vytvořena. Těšíme se na vás."
