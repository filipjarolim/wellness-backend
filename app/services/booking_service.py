from typing import Optional
from sqlmodel import Session, select
from app.models.db_models import Booking

from datetime import datetime, timedelta
import traceback
import logging
from zoneinfo import ZoneInfo

# Import calendar functions
from app.services.calendar_service import check_calendar_availability, create_calendar_event, get_busy_slots, cancel_event_by_description

import json
import os

logger = logging.getLogger(__name__)

CUSTOMERS_FILE = 'data/customers.json'

TZ = ZoneInfo('Europe/Prague')

CZECH_MONTHS = {
    1: "ledna", 2: "února", 3: "března", 4: "dubna", 5: "května", 6: "června",
    7: "července", 8: "srpna", 9: "září", 10: "října", 11: "listopadu", 12: "prosince"
}

class BookingService:
    def __init__(self, session: Session):
        self.session = session
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        if not os.path.exists('data'):
            os.makedirs('data')
        if not os.path.exists(CUSTOMERS_FILE):
            with open(CUSTOMERS_FILE, 'w') as f:
                json.dump({}, f)

    def _load_customers(self) -> dict:
        try:
            with open(CUSTOMERS_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_customers_to_file(self, data: dict):
        with open(CUSTOMERS_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_customer(self, phone: str, name: str):
        if not phone or not name:
            return
        data = self._load_customers()
        data[phone] = name
        self._save_customers_to_file(data)
        logger.info(f"💾 Customer saved: {phone} -> {name}")

    def get_caller_name(self, phone_number: str) -> Optional[str]:
        data = self._load_customers()
        return data.get(phone_number)

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
                 
                 # --- Smart Availability Logic ---
                 alternatives = []
                 window_start = start_dt - timedelta(hours=2)
                 window_end = start_dt + timedelta(hours=2)
                 
                 # Don't suggest times in the past
                 now = datetime.now(TZ)
                 if window_start < now:
                     window_start = now
                 
                 busy_slots = get_busy_slots(window_start, window_end)
                 
                 # Scan 30min slots in the window
                 current_slot = window_start
                 # Round to next 30 min
                 if current_slot.minute < 30:
                     current_slot = current_slot.replace(minute=30, second=0, microsecond=0)
                 else:
                     current_slot = (current_slot + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                     
                 while current_slot < window_end:
                     slot_end = current_slot + timedelta(minutes=60) # Assume 1h booking
                     
                     # Check overlap with busy_slots
                     is_busy = False
                     for b_start, b_end in busy_slots:
                         # Overlap condition: not (SlotEnd <= BusyStart or SlotStart >= BusyEnd)
                         if not (slot_end <= b_start or current_slot >= b_end):
                             is_busy = True
                             break
                     
                     if not is_busy and current_slot != start_dt:
                         alternatives.append(current_slot.strftime("%H:%M"))
                     
                     current_slot += timedelta(minutes=30)
                     if len(alternatives) >= 2: # Found enough alternatives
                         break
                         
                 if alternatives:
                     alt_text = " nebo v ".join(alternatives)
                     return f"Je mi líto, ve {start_dt.strftime('%H:%M')} je plno, ale volno mám v {alt_text}."
                 
                 return f"Je mi líto, ale {formatted_date} je obsazeno a v okolí jsem nenašel volné místo."
             
             # Use ISO format for DB check consistency
             db_day = start_dt.strftime("%Y-%m-%d")
             db_time = start_dt.strftime("%H:%M")

        # 2. Check in DB if there is a booking for this day and time
        # Note: We rely on exact string match if parsing failed, or ISO match if succeeded
        statement = select(Booking).where(Booking.day == db_day, Booking.time == db_time)
        results = self.session.exec(statement)
        existing_booking = results.first()
        
        if existing_booking:
             # Same logic could apply here for DB conflicts, but for now we focus on Calendar conflicts as primary source
            return f"Sorry, {day} at {time} is fully booked."
        
        return f"Ano, {day} v {time} mám volno."

    def cancel_booking(self, phone_number: str) -> str:
        """
        Cancels a booking by looking up events with the phone number in description.
        """
        if not phone_number:
            return "Pro zrušení rezervace potřebuji telefonní číslo."
            
        return cancel_event_by_description(phone_number)

    def book_appointment(self, day: str, time: str, name: str, phone: str = "", service: str = "general") -> str:
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
        
        if phone:
            self.save_customer(phone, name)
        
        logger.info(f"✅ NOVÁ REZERVACE (DB): {name} na {save_day} v {save_time} - {service} (ID: {booking.id})")
        
        # Sync to Google Calendar
        logger.info('🚀 Calling Google Calendar...')
        try:
            # Pass clean datetime object to calendar service
            html_link = create_calendar_event(booking, start_time=start_dt, phone=phone)
            if html_link:
                 logger.info(f"✅ Synced to Calendar: {html_link}")
        except Exception as e:
            logger.error(f"❌ Google Error: {e}") 
            # We don't want to fail the booking if calendar fails, so we just log.
        
        # Format date for user response: "14. ledna 2026"
        month_name = CZECH_MONTHS.get(start_dt.month, "")
        formatted_day = f"{start_dt.day}. {month_name} {start_dt.year}"
        
        return f"Vaše rezervace na jméno {name} na {formatted_day} v {time} byla úspěšně vytvořena. Těšíme se na vás."
