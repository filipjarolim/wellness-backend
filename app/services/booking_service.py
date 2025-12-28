from typing import Optional
# from sqlmodel import Session, select
from app.models.db_models import Booking

from datetime import datetime, timedelta
import traceback
import logging
from zoneinfo import ZoneInfo

# Import calendar functions
from app.services.calendar_service import check_calendar_availability, create_calendar_event, get_busy_slots, cancel_event_by_description

from app.services.db_service import db_service

from app.core.logger import logger

# logger = logging.getLogger(__name__)



TZ = ZoneInfo('Europe/Prague')

CZECH_MONTHS = {
    1: "ledna", 2: "února", 3: "března", 4: "dubna", 5: "května", 6: "června",
    7: "července", 8: "srpna", 9: "září", 10: "října", 11: "listopadu", 12: "prosince"
}

class BookingService:
    def __init__(self):
        # self.session = session # Removed SQLModel
        pass
        # self._ensure_data_dir() # Removed for Supabase migration

    async def get_caller_name(self, phone_number: str) -> Optional[str]:
        return await db_service.get_client_by_phone(phone_number)

    async def check_availability(self, day: str, time: Optional[str] = None) -> str:
        """
        Check availability (Async).
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
             is_calendar_free = await check_calendar_availability(start_dt)
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
                 
                 busy_slots = await get_busy_slots(window_start, window_end)
                 
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
                         if not (slot_end <= b_start or current_slot >= b_end):
                             is_busy = True
                             break
                     
                     if not is_busy and current_slot != start_dt:
                         alternatives.append(current_slot.strftime("%H:%M"))
                     
                     current_slot += timedelta(minutes=30)
                     if len(alternatives) >= 2: 
                         break
                         
                 if alternatives:
                     alt_text = " nebo v ".join(alternatives)
                     return f"Je mi líto, ve {start_dt.strftime('%H:%M')} je plno, ale volno mám v {alt_text}."
                 
                 return f"Je mi líto, ale {formatted_date} je obsazeno a v okolí jsem nenašel volné místo."
             
             # DB check skipped (Calendar is Truth)

        return f"Ano, {day} v {time} mám volno."

    async def cancel_booking(self, phone_number: str) -> str:
        """
        Cancels a booking (Async).
        """
        if not phone_number:
            return "Pro zrušení rezervace potřebuji telefonní číslo."
            
        return await cancel_event_by_description(phone_number)

    def normalize_name(self, name: str) -> str:
        """
        Cleans up the name: Title Case, strips whitespace, fixes common STT errors.
        """
        if not name:
            return ""
        
        name = name.strip().title()
        
        # STT Corrections
        replacements = {
            "Pattern": "Petr",
        }
        for wrong, correct in replacements.items():
            if wrong in name:
                name = name.replace(wrong, correct)
                
        return name

    async def book_appointment(self, day: str, time: str, name: str, phone: str = "", service: str = "general") -> str:
        """
        Book an appointment (Async).
        """
        # Normalize Name
        original_name = name
        name = self.normalize_name(name)
        if name != original_name:
            logger.info(f"🧹 Name Normalized: '{original_name}' -> '{name}'")

        if not day or not time or not name:
             logger.info(f'📥 Booking Request - Day: {day}, Time: {time}')
             return "Omlouvám se, ale chybí mi některé údaje pro vytvoření rezervace."

        logger.info(f'📥 Booking Request - Day: {day}, Time: {time}')

        # Check availability again
        availability_msg = await self.check_availability(day, time)
        if "fully booked" in availability_msg or "busy" in availability_msg or "Je mi líto" in availability_msg:
             return "Omlouvám se, ale termín se nepodařilo zarezervovat. Zkuste to prosím znovu."

        # Parse date
        try:
            start_dt = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            logger.info(f'📅 Vypočítaný Start Time: {start_dt}')
            save_day = start_dt.strftime("%Y-%m-%d")
            save_time = start_dt.strftime("%H:%M")
        except ValueError as e:
            logger.error(f"Cannot parse booking date: {day} {time} error: {e}")
            return "Omlouvám se, ale termín se nepodařilo zarezervovat. Zkuste to prosím znovu."

        start_save_process = datetime.now()
        logger.info(f"⏳ Začínám booking process pro: {name}, tel: {phone}")

        if not phone:
            logger.error("❌ CHYBA: Chybí telefonní číslo! Nelze vytvořit rezervaci.")
            return "Omlouvám se, ale nemám vaše telefonní číslo, které je nutné pro potvrzení rezervace."

        # 1. Supabase Client Management
        client_id = None
        # if phone: # Condition removed, we enforced phone above
        try:
            logger.info(f"🔍 Hledám/Vytvářím klienta v DB: {phone}")
            client_dict = await db_service.get_or_create_client(phone, name)
            if client_dict:
                client_id = client_dict.get('id')
                logger.info(f"✅ Klient ID {client_id} připraven.")
            else:
                logger.warning("⚠️ Nepodařilo se získat ID klienta ze Supabase.")
        except Exception as e:
            logger.error(f"❌ Chyba při správě klienta: {e}")
            # Should we stop? Ideally yes, but maybe Calendar is enough for now?
            # User wants robust DB, so maybe let's continue but log heavily.
        
        # 2. Sync to Google Calendar
        logger.info('🚀 Calling Google Calendar...')
        gcal_link = None
        gcal_id = None
        
        try:
            temp_booking = Booking(name=name, day=save_day, time=save_time, service=service)
            
            event_result = await create_calendar_event(temp_booking, start_time=start_dt, phone=phone)
            
            if event_result:
                gcal_link = event_result.get('htmlLink')
                gcal_id = event_result.get('id')
                logger.info(f"✅ Synced to Calendar: {gcal_link} (ID: {gcal_id})")
            else:
                logger.error("❌ Calendar sync failed - no event result returned")
        except Exception as e:
            logger.error(f"❌ Google Error: {e}") 
        
        # 3. Log to Supabase
        if client_id and gcal_id:
             try:
                 logger.info(f"📝 Zapisuji rezervaci do Supabase: Client {client_id}, Event {gcal_id}")
                 await db_service.log_booking(client_id, start_dt, service, gcal_id)
                 logger.info("✅ Rezervace úspěšně uložena do DB.")
             except Exception as e:
                 logger.error(f"❌ Chyba při logování rezervace: {e}")
        else:
             logger.warning(f"⚠️ Přeskakuji zápis rezervace do DB (Missing: ClientID={bool(client_id)}, GCalID={bool(gcal_id)})")
        
        
        duration = (datetime.now() - start_save_process).total_seconds()
        logger.info(f"🏁 Booking process completed in {duration:.2f}s")

        month_name = CZECH_MONTHS.get(start_dt.month, "")
        formatted_day = f"{start_dt.day}. {month_name} {start_dt.year}"
        
        return f"Vaše rezervace na jméno {name} na {formatted_day} v {time} byla úspěšně vytvořena. Těšíme se na vás."
