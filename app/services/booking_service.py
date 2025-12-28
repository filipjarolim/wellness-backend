from typing import Optional
from sqlmodel import Session, select
from app.models.db_models import Booking

from datetime import datetime, timedelta
import traceback

# Import calendar functions
from app.services.calendar_service import check_calendar_availability, create_calendar_event

class BookingService:
    def __init__(self, session: Session):
        self.session = session

    def _parse_datetime(self, day_str: str, time_str: str) -> Optional[datetime]:
        """
        Parse natural language day (Monday, pondělí) or date to datetime.
        Returns None if parsing fails.
        """
        try:
            # 1. Try ISO format first (YYYY-MM-DD)
            return datetime.fromisoformat(f"{day_str}T{time_str}:00")
        except ValueError:
            pass
            
        try:
            # 2. Handle Day Names (English + Czech)
            days_map = {
                'monday': 0, 'pondělí': 0, 'pondeli': 0,
                'tuesday': 1, 'úterý': 1, 'utery': 1,
                'wednesday': 2, 'středa': 2, 'streda': 2,
                'thursday': 3, 'čtvrtek': 3, 'ctvrtek': 3,
                'friday': 4, 'pátek': 4, 'patek': 4,
                'saturday': 5, 'sobota': 5,
                'sunday': 6, 'neděle': 6, 'nedele': 6
            }
            
            day_lower = day_str.lower().strip()
            if day_lower in days_map:
                target_idx = days_map[day_lower]
                now = datetime.now()
                today_idx = now.weekday()
                
                # Calculate days ahead
                days_ahead = (target_idx - today_idx + 7) % 7
                
                # If it's today, check if time has passed. If so, move to next week?
                # For simplicity, keeping explicit logic requested: just find nearest day.
                # If days_ahead == 0 (It is today), we assume today.
                # Only if we wanted strict future, we'd add 7. 
                # Let's add 7 if days_ahead is 0 AND time is passed? 
                # User instructions: "Zjisti index... a přičti potřebný počet dní."
                # We'll stick to basic forward look.
                
                target_date = now + timedelta(days=days_ahead)
                
                # Compose datetime
                h, m = map(int, time_str.split(':'))
                dt = target_date.replace(hour=h, minute=m, second=0, microsecond=0)
                
                # If the resulting time is in the past (e.g. today earlier), add 7 days
                if dt < now:
                    dt += timedelta(days=7)
                    
                return dt

            # 3. Try simple date format DD.MM.
            current_year = datetime.now().year
            clean_day = day_str.strip().rstrip('.')
            day_part, month_part = clean_day.split('.')
            dt = datetime(year=current_year, month=int(month_part), day=int(day_part))
            h, m = map(int, time_str.split(':'))
            return dt.replace(hour=h, minute=m, second=0, microsecond=0)

        except Exception as e:
            print(f"⚠️ Date parsing failed inside helper for {day_str} {time_str}: {e}")
            return None

    def check_availability(self, day: str, time: Optional[str] = None) -> str:
        """
        Check availability for a given day and optionally a time from the DB and Google Calendar.
        """
        if not time:
            return f"Checking generic availability for {day} is not fully implemented yet."
        
        start_dt = self._parse_datetime(day, time)

        if start_dt:
             # Check Google Calendar
             is_calendar_free = check_calendar_availability(start_dt)
             if not is_calendar_free:
                 formatted_date = start_dt.strftime("%d.%m. %H:%M")
                 return f"Sorry, {formatted_date} is busy in the calendar."
             
             # Use ISO format for DB check consistency
             # (Assume DB stores ISO string YYYY-MM-DD and HH:MM)
             db_day = start_dt.strftime("%Y-%m-%d")
             db_time = start_dt.strftime("%H:%M")
        else:
            # Fallback to direct string matching if parsing failed (unlikely for DB but possible)
            db_day = day
            db_time = time

        # 2. Check in DB if there is a booking for this day and time
        # Note: We rely on exact string match if parsing failed, or ISO match if succeeded
        statement = select(Booking).where(Booking.day == db_day, Booking.time == db_time)
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
             print(f'📥 Booking Request - Day: {day}, Time: {time}', flush=True)
             return {"result": "error", "message": "Missing details for booking."}

        print(f'📥 Booking Request - Day: {day}, Time: {time}', flush=True)

        # Check availability again
        availability_msg = self.check_availability(day, time)
        if "fully booked" in availability_msg or "busy" in availability_msg:
             return {"result": "error", "message": f"Time slot {day} {time} is already booked."}

        # Parse date for storage normalization and Calendar
        start_dt = self._parse_datetime(day, time)
        print(f'📅 Vypočítaný Start Time: {start_dt}', flush=True)
        
        # Decide what to save to DB. Ideally ISO format.
        if start_dt:
            save_day = start_dt.strftime("%Y-%m-%d")
            save_time = start_dt.strftime("%H:%M")
            print(f"📅 Parsed Date: {start_dt}")
        else:
            save_day = day
            save_time = time
            print(f"⚠️ Could not parse date, saving raw strings: {day} {time}")

        # Create DB record
        booking = Booking(name=name, day=save_day, time=save_time, service=service)
        self.session.add(booking)
        self.session.commit()
        self.session.refresh(booking)
        
        print(f"✅ NOVÁ REZERVACE (DB): {name} na {save_day} v {save_time} - {service} (ID: {booking.id})")
        
        # Sync to Google Calendar
        print('🚀 Calling Google Calendar...', flush=True)
        try:
            # Modify booking object to ensure ISO format is used for Calendar creation logic 
            # (although we already saved ISO to DB if parsing succeeded)
            # The calendar service will re-parse, but since we now provide ISO, it should pass.
            html_link = create_calendar_event(booking)
            if html_link:
                 print(f"✅ Synced to Calendar: {html_link}", flush=True)
        except Exception as e:
            print(f"❌ Google Error: {e}", flush=True)
            traceback.print_exc()
        
        return {"result": "success", "message": "Termín je úspěšně rezervován."}
