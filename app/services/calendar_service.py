import os
import json
import datetime
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.models.db_models import Booking

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'google_credentials.json'

def get_calendar_service():
    """
    Authenticate and return the Google Calendar service.
    Supports loading credentials from:
    1. 'google_credentials.json' file (local development).
    2. 'GOOGLE_CREDENTIALS_JSON' env variable (cloud deployment).
    Returns None if credentials are missing or invalid.
    """
    creds = None
    
    print('🔑 Zkouším načíst credentials...', flush=True)

    try:
        # 1. Try file
        if os.path.exists(CREDENTIALS_FILE):
             print(f"🔑 Loading credentials from file: {CREDENTIALS_FILE}", flush=True)
             print('✅ Načteno ze souboru.', flush=True)
             creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_FILE, scopes=SCOPES
             )
        # 2. Try Env Var
        elif os.environ.get('GOOGLE_CREDENTIALS_JSON'):
             print("🔑 Loading credentials from Environment Variable", flush=True)
             print('✅ Načteno z ENV (GOOGLE_CREDENTIALS_JSON).', flush=True)
             info = json.loads(os.environ.get('GOOGLE_CREDENTIALS_JSON'))
             creds = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
             )
        else:
            print("⚠️ Warning: No Google credentials found (file or env). Calendar sync skipped.", flush=True)
            return None

        print(f'🤖 Service Account Email: {creds.service_account_email}', flush=True)

        service = build('calendar', 'v3', credentials=creds)
        return service

    except Exception as e:
        print(f"❌ Error initializing Google Calendar service: {e}", flush=True)
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

    time_min = start_time.isoformat() + 'Z'  # 'Z' indicates UTC time
    time_max = (start_time + datetime.timedelta(minutes=duration_minutes)).isoformat() + 'Z'

    try:
        events_result = service.events().list(
            calendarId='primary', 
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
        print(f"❌ Error checking calendar availability: {e}")
        # Default to True so we don't block bookings if API fails, 
        # but in strict mode we might want to return False
        return True

def create_calendar_event(booking: Booking, duration_minutes: int = 60) -> Optional[str]:
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

    except ValueError:
        # Fallback if parsing fails (e.g. "tomorrow")
        # In a real scenario we'd use dateparser. 
        # For safety, let's log and return.
        print(f"⚠️ Could not parse date/time for calendar: {booking.day} {booking.time}")
        return None

    end_time = start_time + datetime.timedelta(minutes=duration_minutes)

    event_body = {
        'summary': f"{booking.name} - {booking.service}",
        'location': 'Wellness Pohoda',
        'description': 'Rezervace přes AI Asistenta',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'Europe/Prague', # Adjust as needed
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'Europe/Prague',
        },
    }

    try:
        print(f'📤 Odesílám event: {event_body}', flush=True)
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        print(f"📅 Event created: {event.get('htmlLink')}")
        return event.get('htmlLink')
        return event.get('htmlLink')
    except HttpError as error:
        print(f'❌ Google API Error: {error.content}', flush=True)
        return None
    except Exception as e:
        print(f"❌ Error creating calendar event: {e}", flush=True)
        return None
