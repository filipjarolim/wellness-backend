from supabase import create_client, Client
from app.core.config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DBService:
    _instance = None
    _client: Client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBService, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        try:
            if settings.SUPABASE_URL and settings.SUPABASE_KEY:
                self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logger.info("✅ Supabase client initialized")
            else:
                logger.warning("⚠️ Supabase credentials missing")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase: {e}")

    def get_or_create_client(self, phone: str, name: str) -> dict:
        """
        Finds a client by phone. If not found, creates a new one.
        Returns dict with client 'id' and 'name'.
        """
        if not self._client:
            return None

        try:
            # Check if exists
            response = self._client.table('clients').select("*").eq('phone', phone).execute()
            
            if response.data:
                client = response.data[0]
                logger.debug(f"found client: {client}")
                # Optionally update name if changed? For now, just return.
                return {'id': client['id'], 'name': client['name']}
            
            # Create new
            new_client = {'phone': phone, 'name': name}
            response = self._client.table('clients').insert(new_client).execute()
            
            if response.data:
                logger.info(f"🆕 New client created: {name} ({phone})")
                return {'id': response.data[0]['id'], 'name': response.data[0]['name']}
            
        except Exception as e:
            logger.error(f"❌ DB Error (get_or_create_client): {e}")
            return None

    def get_client_by_phone(self, phone: str) -> str:
        """
        Returns client name or None.
        """
        if not self._client:
            return None
            
        try:
            response = self._client.table('clients').select("name").eq('phone', phone).execute()
            if response.data:
                return response.data[0]['name']
        except Exception as e:
            logger.error(f"❌ DB Error (get_client_by_phone): {e}")
            
        return None

    def log_booking(self, client_id: int, time: datetime, service_type: str, gcal_id: str):
        """
        Logs a booking to the database.
        """
        if not self._client or not client_id:
            return

        try:
            booking_data = {
                'client_id': client_id,
                'booking_time': time.isoformat(),
                'service_type': service_type,
                'gcal_event_id': gcal_id,
                'created_at': datetime.now().isoformat()
            }
            
            response = self._client.table('bookings').insert(booking_data).execute()
            if response.data:
                logger.info(f"✅ Booking logged to DB for client {client_id}")
                
        except Exception as e:
            logger.error(f"❌ DB Error (log_booking): {e}")

db_service = DBService()
