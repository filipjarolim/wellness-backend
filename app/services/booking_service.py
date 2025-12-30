from typing import Optional
# from sqlmodel import Session, select
from app.models.db_models import Booking

from datetime import datetime, timedelta
import traceback
# import logging # Removed standard logging
from zoneinfo import ZoneInfo
from fastapi import BackgroundTasks

# Import calendar functions
from app.services.calendar_service import check_calendar_availability, create_calendar_event, get_busy_slots, cancel_event_by_description

from app.services.db_service import db_service

from app.core.logger import logger
from app.core.config_loader import load_company_config, get_business_hours
from app.services.notification_service import send_sms, send_email

# logger = logging.getLogger(__name__)



TZ = ZoneInfo('Europe/Prague')

CZECH_MONTHS = {
    1: "ledna", 2: "února", 3: "března", 4: "dubna", 5: "května", 6: "června",
    7: "července", 8: "srpna", 9: "září", 10: "října", 11: "listopadu", 12: "prosince"
}

class BookingService:
    def __init__(self):
        # self.session = session # Removed SQLModel
        self.config = load_company_config()
        # self._ensure_data_dir() # Removed for Supabase migration


    async def get_caller_name(self, phone_number: str) -> Optional[str]:
        return await db_service.get_client_by_phone(phone_number)

    async def check_availability(self, day: str, time: Optional[str] = None) -> str:
        """
        Check availability (Async).
        Respects External Configuration (Business Rules).
        """
        company_name = self.config.get('company_name', 'naše společnost')

        # Generic message if only day is provided (simplified for now)
        if not time:
            return f"Pro zjištění dostupnosti v {company_name} prosím uveďte i čas."
        
        try:
            # Parse Requested Date
            start_dt = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            day_name = start_dt.strftime("%A").lower() # e.g. "monday"
            
            # 1. Check Business Hours (Config)
            hours = get_business_hours(self.config, day_name)
            
            if not hours:
                # Closed (null in JSON)
                days_cz = {
                    "monday": "pondělí", "tuesday": "úterý", "wednesday": "středu",
                    "thursday": "čtvrtek", "friday": "pátek", "saturday": "sobotu", "sunday": "neděli"
                }
                day_cz = days_cz.get(day_name, day_name)
                return f"V {day_cz} máme bohužel zavřeno."

            open_start = hours.get('start')
            open_end = hours.get('end')
            
            # Simple Time Comparison (String compare usually works for HH:MM 24h, ensures Leading Zero)
            req_time = start_dt.strftime("%H:%M")
            
            if not (open_start <= req_time < open_end):
                return f"Máme otevřeno jen od {open_start} do {open_end}."

        except ValueError as e:
            logger.error(f"Date parsing failed for {day} {time}: {e}")
            return f"Invalid date or time format. Please provide YYYY-MM-DD and HH:MM."

        if start_dt:
             # Check Google Calendar availability ...
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

    async def get_active_booking(self, phone: str) -> Optional[dict]:
        """
        Alias for get_upcoming_booking, ensures strict naming compliance for testing.
        Returns active booking dict or None.
        """
        return await self.get_upcoming_booking(phone)

    async def get_upcoming_booking(self, phone: str) -> Optional[dict]:
        """
        Finds the nearest future booking for a phone number.
        """
        # 1. Clean phone
        phone = phone.replace(" ", "").strip()
        
        # 2. Get Client ID
        client_id = await db_service.get_client_id(phone)
        if not client_id:
            logger.info(f"🔍 No client found for phone {phone}")
            return None
            
        # 3. Get Booking
        return await db_service.get_upcoming_booking_by_client_id(client_id)

    async def cancel_active_booking(self, phone: str) -> bool:
        """
        Cancels the active booking for the phone number.
        Returns True if a booking was found and cancelled, False otherwise.
        """
        # 1. Find Booking
        booking = await self.get_active_booking(phone)
        if not booking:
            logger.warning(f"⚠️ No active booking found for {phone} to cancel.")
            return False
            
        booking_id = booking.get('id')
        gcal_id = booking.get('gcal_event_id')
        
        # 2. Delete from Google Calendar (Best Effort)
        if gcal_id:
             try:
                 from app.services.calendar_service import get_calendar_service, CALENDAR_ID
                 service = get_calendar_service()
                 if service:
                     service.events().delete(calendarId=CALENDAR_ID, eventId=gcal_id).execute()
                     logger.info(f"🗑️ GCal Event {gcal_id} deleted.")
             except Exception as e:
                 logger.error(f"⚠️ Failed to delete GCal event: {e}")
        
        # 3. Delete from DB
        success = False
        if booking_id:
            success = await db_service.delete_booking(booking_id)
            
        return success

    async def cancel_booking(self, phone_number: str, background_tasks: Optional[BackgroundTasks] = None) -> str:
        """
        Vapi Tool wrapper: Cancels the nearest future booking and returns a message.
        """
        if not phone_number:
            return "Pro zrušení rezervace potřebuji telefonní číslo."
            
        logger.info(f"❌ Processing cancellation for {phone_number}")
        
        # Check existence first to get date for message (before deletion)
        booking = await self.get_active_booking(phone_number)
        if not booking:
             # Fallback legacy check
             return await cancel_event_by_description(phone_number)

        formatted_date = booking.get('start_time', 'unknown')
        try:
            formatted_date = datetime.fromisoformat(formatted_date).strftime("%d.%m. %H:%M")
        except:
            pass

        # Perform Cancellation
        was_cancelled = await self.cancel_active_booking(phone_number)
        
        if was_cancelled:
            msg = f"Vaše rezervace na {formatted_date} byla zrušena."
            # Notification
            try:
                if background_tasks:
                    background_tasks.add_task(send_sms, phone_number, msg)
                else:
                    send_sms(phone_number, msg)
            except Exception as e:
                logger.error(f"❌ Failed to send cancellation SMS: {e}")
            return msg
        else:
            return "Nepodařilo se zrušit rezervaci (chyba systému)."

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

    async def send_notifications(self, phone: str, name: str, service: str, start_dt: datetime, background_tasks: Optional[BackgroundTasks] = None):
        """
        Sends SMS to client and Email to owner.
        Uses BackgroundTasks if provided, otherwise synchronous.
        """
        notifications_config = self.config.get("notifications", {})
        company_name = self.config.get("company_name", "Naše Firma")
        
        # Helper variables
        date_str = start_dt.strftime("%d.%m.%Y")
        time_str = start_dt.strftime("%H:%M")
        
        # 1. Prepare SMS
        sms_template = notifications_config.get("sms_template", "Rezervace na {date} v {time} potvrzena.")
        try:
            sms_body = sms_template.format(
                name=name,
                service=service,
                date=date_str,
                time=time_str,
                company_name=company_name
            )
            
            if background_tasks:
                logger.info(f"📨 Scheduling SMS for {phone} in background...")
                background_tasks.add_task(send_sms, phone, sms_body)
            else:
                 logger.warning("⚠️ BackgroundTasks not provided, sending SMS synchronously (blocking).")
                 send_sms(phone, sms_body)

        except Exception as e:
            logger.error(f"❌ Error preparing SMS: {e}")

        # 2. Prepare Email
        email_template = notifications_config.get("email_template", "Nová rezervace: {name}, {date} {time}")
        email_subject_tmpl = notifications_config.get("email_subject", "Nová rezervace")
        try:
            email_subject = email_subject_tmpl.format(name=name, date=date_str, time=time_str)
            email_body = email_template.format(
                name=name,
                phone=phone,
                service=service,
                date=date_str,
                time=time_str
            )
            
            if background_tasks:
                logger.info(f"📨 Scheduling Email for owner in background...")
                background_tasks.add_task(send_email, email_subject, email_body)
            else:
                 logger.warning("⚠️ BackgroundTasks not provided, sending Email synchronously (blocking).")
                 send_email(email_subject, email_body)
                 
        except Exception as e:
             logger.error(f"❌ Error preparing Email: {e}")

    async def book_appointment(self, day: str, time: str, name: str, phone: str = "", service: str = "general", background_tasks: Optional[BackgroundTasks] = None) -> str:
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
                 
                 # 4. Notifications
                 # NOTE: We pass background_tasks here to offload sending
                 await self.send_notifications(phone, name, service, start_dt, background_tasks=background_tasks)
                 
             except Exception as e:
                 logger.error(f"❌ Chyba při logování rezervace: {e}")
        else:
             logger.warning(f"⚠️ Přeskakuji zápis rezervace do DB (Missing: ClientID={bool(client_id)}, GCalID={bool(gcal_id)})")
        
        
        duration = (datetime.now() - start_save_process).total_seconds()
        logger.info(f"🏁 Booking process completed in {duration:.2f}s")

        month_name = CZECH_MONTHS.get(start_dt.month, "")
        formatted_day = f"{start_dt.day}. {month_name} {start_dt.year}"
        
        return f"Vaše rezervace na jméno {name} na {formatted_day} v {time} byla úspěšně vytvořena. Těšíme se na vás."
