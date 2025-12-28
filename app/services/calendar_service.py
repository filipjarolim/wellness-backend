import os
import json
import datetime
from typing import Optional
import logging
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.models.db_models import Booking

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'google_credentials.json'
CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
PRAGUE_TZ = ZoneInfo('Europe/Prague')
UTC = ZoneInfo('UTC')

logger = logging.getLogger(__name__)

def get_calendar_service():
    """
    Authenticate and return the Google Calendar service.
    Supports loading credentials from:
    1. 'google_credentials.json' file (local development).
    2. 'GOOGLE_CREDENTIALS_JSON' env variable (cloud deployment).
    Returns None if credentials are missing or invalid.
    """
    creds = None
    
    logger.info('🔑 Zkouším načíst credentials...')

    try:
        # 1. Try file
        if os.path.exists(CREDENTIALS_FILE):
             logger.info(f"🔑 Loading credentials from file: {CREDENTIALS_FILE}")
             logger.info('✅ Načteno ze souboru.')
             creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_FILE, scopes=SCOPES
             )
        # 2. Try Env Var
        elif os.environ.get('GOOGLE_CREDENTIALS_JSON'):
             logger.info("🔑 Loading credentials from Environment Variable")
             logger.info('✅ Načteno z ENV (GOOGLE_CREDENTIALS_JSON).')
             info = json.loads(os.environ.get('GOOGLE_CREDENTIALS_JSON'))
             creds = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
             )
        else:
            logger.warning("⚠️ Warning: No Google credentials found (file or env). Calendar sync skipped.")
            return None

        logger.info(f'🤖 Service Account Email: {creds.service_account_email}')

        service = build('calendar', 'v3', credentials=creds)
        return service

    except Exception as e:
        logger.error(f"❌ Error initializing Google Calendar service: {e}")
        return None

def check_calendar_availability(start_time: datetime.datetime, duration_minutes: int = 60) -> bool:
    """
    Check if the time slot is free in the primary calendar.
    Returns True if available, False if busy.
    """
    service = get_calendar_service()
    if not service:
        # Fallback: if no calendar service, assume available (or handle otherwise)
        # For safety in MVP, maybe we assume available and rely on internal DB
        return True

        return True

    # Ensure start_time is timezone aware
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=PRAGUE_TZ)
    
    time_min = start_time.isoformat()
    time_max = (start_time + datetime.timedelta(minutes=duration_minutes)).isoformat()

    try:
        logger.debug(f'🔍 Kontroluji dostupnost v kalendáři: {CALENDAR_ID}')
        events_result = service.events().list(
            calendarId=CALENDAR_ID, 
            timeMin=time_min, 
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if events:
            return False # Found conflicting events
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking calendar availability: {e}")
        # Default to True so we don't block bookings if API fails, 
        # but in strict mode we might want to return False
        return True
    
    except Exception as e:
        logger.error(f"❌ Error checking calendar availability: {e}")
        return True

def get_busy_slots(start_time: datetime.datetime, end_time: datetime.datetime) -> list:
    """
    Returns a list of busy time ranges (tuples of start, end datetime) 
    between start_time and end_time.
    """
    service = get_calendar_service()
    if not service:
        return []

    # Ensure timezones
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=PRAGUE_TZ)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=PRAGUE_TZ)

    time_min = start_time.isoformat()
    time_max = end_time.isoformat()

    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID, 
            timeMin=time_min, 
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        busy_slots = []
        for event in events:
            start = event['start'].get('dateTime') or event['start'].get('date')
            end = event['end'].get('dateTime') or event['end'].get('date')
            
            # Simple parsing of ISO strings
            # Google API returns ISO strings, e.g. "2025-01-14T14:00:00+01:00"
            if start and end:
                try:
                    s_dt = datetime.datetime.fromisoformat(start)
                    e_dt = datetime.datetime.fromisoformat(end)
                    busy_slots.append((s_dt, e_dt))
                except ValueError:
                    continue # Skip full-day events or weird formats if parsing fails
                    
        return busy_slots

    except Exception as e:
        logger.error(f"❌ Error getting busy slots: {e}")
        return []

    except Exception as e:
        logger.error(f"❌ Error getting busy slots: {e}")
        return []

def cancel_event_by_description(phone_number: str) -> str:
    """
    Finds future events with the given phone number in description and deletes them.
    Returns a status message.
    """
    service = get_calendar_service()
    if not service:
        return "Služba kalendáře není dostupná."

    now = datetime.datetime.now(PRAGUE_TZ)
    time_min = now.isoformat()
    
    try:
        # List future events
        events_result = service.events().list(
            calendarId=CALENDAR_ID, 
            timeMin=time_min, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        found_and_deleted = False
        deleted_date = ""

        for event in events:
            desc = event.get('description', '')
            if phone_number in desc:
                # Found it!
                start = event['start'].get('dateTime') or event['start'].get('date')
                event_id = event['id']
                
                # Delete
                service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
                logger.info(f"🗑️ Smazán event: {event.get('summary')} ({start})")
                
                found_and_deleted = True
                # Format date for user
                try:
                    dt = datetime.datetime.fromisoformat(start)
                    deleted_date = dt.strftime("%d.%m. %H:%M")
                except:
                    deleted_date = start
                    
                # We stop after first match? Or delete all? 
                # Prompt says "Pokud najde, smaže událost" (singular?). 
                # Usually better to delete one specific or all future? 
                # Let's assume one booking active usually, or delete all future.
                # "Vaše rezervace na [DATUM] byla zrušena." implies one.
                break 
        
        if found_and_deleted:
            return f"Vaše rezervace na {deleted_date} byla zrušena."
        else:
            return "Na toto číslo nemám žádnou rezervaci."

    except Exception as e:
        logger.error(f"❌ Error cancelling event: {e}")
        return "Došlo k chybě při rušení rezervace."

def create_calendar_event(booking: Booking, duration_minutes: int = 60, start_time: Optional[datetime.datetime] = None, phone: str = "") -> Optional[dict]:
    """
    Create an event in Google Calendar.
    Returns the htmlLink of the event or None.
    """
    service = get_calendar_service()
    if not service:
        return None

    # Parse booking day/time to datetime
    # Assumes booking.day is YYYY-MM-DD and booking.time is HH:MM
    # If using 'tomorrow' strings, this needs parsing logic. 
    # For now, let's assume the BookingService or caller converts to real dates, 
    # OR we handle simple parsing here.
    
    if start_time:
        # Use provided datetime object
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=PRAGUE_TZ)
    else:
        # Fallback parsing (should be avoided now)
        try:
            # Very basic parsing for MVP (assuming strict format, or we might fail)
            # In a real app, ensure date/time are standard before calling this.
            # But wait, Booking model has strings. 
            # We need a robust parser or rely on strict inputs.
            # Let's try to parse common ISO formats `YYYY-MM-DD` `HH:MM`
            start_dt_str = f"{booking.day}T{booking.time}:00"
            
            # Determine if we have a simplistic "tomorrow" string or a date
            # If the user used 'tomorrow', this will crash unless we normalize earlier.
            # Assuming for this step that we receive valid ISO strings or handled elsewhere?
            # The prompt asked for `check_calendar_availability(start_time: datetime, ...)`
            # so caller must provide datetime. 
            # But `create_calendar_event` takes `Booking` object which has strings.
            # We will attempt basic ISO parsing.
            
            start_time = datetime.datetime.fromisoformat(start_dt_str)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=PRAGUE_TZ)

        except ValueError:
            pass # Handle below
            
        if 'start_time' not in locals():
             logger.warning(f"⚠️ Could not parse date/time for calendar: {booking.day} {booking.time}")
             return None

    # Calculate end time in local time first
    end_time = start_time + datetime.timedelta(minutes=duration_minutes)

    # Convert to UTC for Google API to prevent timezone shifting issues
    start_utc = start_time.astimezone(UTC)
    end_utc = end_time.astimezone(UTC)

    description = 'Rezervace přes AI Asistenta'
    if phone:
        description += f"\nTelefon: {phone}"

    event_body = {
        'summary': f"{booking.name} - {booking.service}",
        'location': 'Wellness Pohoda',
        'description': description,
        'start': {
            'dateTime': start_utc.isoformat().replace('+00:00', 'Z'),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_utc.isoformat().replace('+00:00', 'Z'),
            'timeZone': 'UTC',
        },
    }

    try:
        logger.info(f'✏️ Zapisuji do kalendáře: {CALENDAR_ID}')
        logger.debug(f'📤 Odesílám event: {event_body}')
        event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        logger.info(f"📅 Event created: {event.get('htmlLink')}")
        return {'id': event.get('id'), 'htmlLink': event.get('htmlLink')}
    except HttpError as error:
        logger.error(f'❌ Google API Error: {error.content}')
        raise RuntimeError(f"Google API Error: {error.content}")
    except Exception as e:
        logger.error(f"❌ Error creating calendar event: {e}")
        return None
