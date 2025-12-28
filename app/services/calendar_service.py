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

import asyncio

# ... imports ...

async def check_calendar_availability(start_time: datetime.datetime, duration_minutes: int = 60) -> bool:
    """
    Check if the time slot is free in the primary calendar.
    Returns True if available, False if busy.
    """
    # service creation might be blocking too (reading file), but usually fast. 
    # Ideally get_calendar_service should be outside loop or cached. 
    # For now, wrap the whole logic or just the execute part.
    
    def _check():
        service = get_calendar_service()
        if not service:
            return True # Fallback

        # Ensure start_time is timezone aware
        st = start_time
        if st.tzinfo is None:
            st = st.replace(tzinfo=PRAGUE_TZ)
        
        time_min = st.isoformat()
        time_max = (st + datetime.timedelta(minutes=duration_minutes)).isoformat()

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
            return True

    return await asyncio.to_thread(_check)

async def get_busy_slots(start_time: datetime.datetime, end_time: datetime.datetime) -> list:
    """
    Returns a list of busy time ranges.
    """
    def _get():
        service = get_calendar_service()
        if not service:
            return []

        st = start_time
        et = end_time
        if st.tzinfo is None: st = st.replace(tzinfo=PRAGUE_TZ)
        if et.tzinfo is None: et = et.replace(tzinfo=PRAGUE_TZ)

        time_min = st.isoformat()
        time_max = et.isoformat()

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
                
                if start and end:
                    try:
                        s_dt = datetime.datetime.fromisoformat(start)
                        e_dt = datetime.datetime.fromisoformat(end)
                        busy_slots.append((s_dt, e_dt))
                    except ValueError:
                        continue 
                        
            return busy_slots

        except Exception as e:
            logger.error(f"❌ Error getting busy slots: {e}")
            return []

    return await asyncio.to_thread(_get)

async def cancel_event_by_description(phone_number: str) -> str:
    """
    Finds future events with the given phone number in description and deletes them.
    """
    def _cancel():
        service = get_calendar_service()
        if not service:
            return "Služba kalendáře není dostupná."

        now = datetime.datetime.now(PRAGUE_TZ)
        time_min = now.isoformat()
        
        try:
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
                    start = event['start'].get('dateTime') or event['start'].get('date')
                    event_id = event['id']
                    
                    service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
                    logger.info(f"🗑️ Smazán event: {event.get('summary')} ({start})")
                    
                    found_and_deleted = True
                    try:
                        dt = datetime.datetime.fromisoformat(start)
                        deleted_date = dt.strftime("%d.%m. %H:%M")
                    except:
                        deleted_date = start
                    break 
            
            if found_and_deleted:
                return f"Vaše rezervace na {deleted_date} byla zrušena."
            else:
                return "Na toto číslo nemám žádnou rezervaci."

        except Exception as e:
            logger.error(f"❌ Error cancelling event: {e}")
            return "Došlo k chybě při rušení rezervace."

    return await asyncio.to_thread(_cancel)

async def create_calendar_event(booking: Booking, duration_minutes: int = 60, start_time: Optional[datetime.datetime] = None, phone: str = "") -> Optional[dict]:
    """
    Create an event in Google Calendar (Async).
    """
    def _create():
        service = get_calendar_service()
        if not service:
            return None

        # Parse booking day/time to datetime if logic requires... 
        # Here we rely on start_time being passed or parsed in sync block
        
        st = start_time
        if st is None:
             # Fallback parsing inside thread
            try:
                start_dt_str = f"{booking.day}T{booking.time}:00"
                st = datetime.datetime.fromisoformat(start_dt_str)
                if st.tzinfo is None:
                    st = st.replace(tzinfo=PRAGUE_TZ)
            except ValueError:
                pass
        
        if st is None:
             logger.warning(f"⚠️ Could not parse date/time for calendar")
             return None
        
        # Calculate end time
        end_time = st + datetime.timedelta(minutes=duration_minutes)

        # Convert to UTC
        start_utc = st.astimezone(UTC)
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
            event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
            logger.info(f"📅 Event created: {event.get('htmlLink')}")
            return {'id': event.get('id'), 'htmlLink': event.get('htmlLink')}
        except HttpError as error:
            logger.error(f'❌ Google API Error: {error.content}')
            raise RuntimeError(f"Google API Error: {error.content}")
        except Exception as e:
            logger.error(f"❌ Error creating calendar event: {e}")
            return None

    return await asyncio.to_thread(_create)
