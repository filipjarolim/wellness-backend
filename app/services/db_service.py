from supabase import create_async_client, AsyncClient
from app.core.config import settings
import logging
from datetime import datetime

logger = logging.getLogger("app")

class DBService:
    _instance = None
    _client: AsyncClient = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBService, cls).__new__(cls)
            # Async client init is tricky in __new__ (sync), will init on first usage or explicit init
        return cls._instance

    async def get_client(self):
        if not self._client:
            try:
                if settings.SUPABASE_URL and settings.SUPABASE_KEY:
                    self._client = await create_async_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                    logger.info("✅ Supabase Async client initialized")
                else:
                    logger.warning("⚠️ Supabase credentials missing")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Supabase Async: {e}")
        return self._client

    async def get_or_create_client(self, phone: str, name: str) -> dict:
        """
        Finds a client by phone. If not found, creates a new one.
        Smart Logic: Updates name if better/longer name is provided.
        """
        client = await self.get_client()
        if not client:
            return None

        try:
            # Check if exists
            response = await client.table('clients').select("*").eq('phone_number', phone).execute()
            
            if response.data:
                client_data = response.data[0]
                existing_name = client_data.get('full_name') or ""
                final_name = existing_name

                # Smart Name Update: If new name is provided and is longer (e.g. "Petr" -> "Petr Novák")
                if name and len(name.strip()) > len(existing_name.strip()):
                    try:
                        await client.table('clients').update({'full_name': name}).eq('id', client_data['id']).execute()
                        logger.info(f"✨ Vylepšuji jméno klienta (ID {client_data['id']}): '{existing_name}' -> '{name}'")
                        final_name = name
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to update client name: {e}")
                
                return {'id': client_data['id'], 'name': final_name}
            
            # Create new
            new_client = {'phone_number': phone, 'full_name': name}
            response = await client.table('clients').insert(new_client).execute()
            
            if response.data:
                logger.info(f"🆕 New client created: {name} ({phone})")
                return {'id': response.data[0]['id'], 'name': response.data[0].get('full_name', name)}
            
        except Exception as e:
            logger.error(f"❌ DB Error (get_or_create_client): {e}")
            return None

    async def get_client_by_phone(self, phone: str) -> str:
        """
        Returns client name or None.
        """
        client = await self.get_client()
        if not client:
            return None
            
        try:
            response = await client.table('clients').select("full_name").eq('phone_number', phone).execute()
            if response.data:
                return response.data[0]['full_name']
        except Exception as e:
            logger.error(f"❌ DB Error (get_client_by_phone): {e}")
            
        return None

    async def log_booking(self, client_id: int, time: datetime, service_type: str, gcal_id: str):
        """
        Logs a booking to the database.
        """
        client = await self.get_client()
        if not client or not client_id:
            return

        try:
            booking_data = {
                'client_id': client_id,
                'start_time': time.isoformat(),
                'service_type': service_type,
                'gcal_event_id': gcal_id
            }
            
            response = await client.table('bookings').insert(booking_data).execute()
            if response.data:
                logger.info(f"✅ Booking logged to DB for client {client_id}")
                
        except Exception as e:
            logger.error(f"❌ DB Error (log_booking): {e}")

    async def get_client_id(self, phone: str) -> int:
        """Helper to get client ID from phone (if exists)."""
        client = await self.get_client()
        if not client: return None
        try:
             response = await client.table('clients').select("id").eq('phone_number', phone).execute()
             if response.data:
                 return response.data[0]['id']
        except Exception:
             return None
        return None

    async def get_upcoming_booking_by_client_id(self, client_id: int) -> dict:
        """
        Returns the nearest future booking for the client.
        """
        client = await self.get_client()
        if not client: return None
        
        try:
            now_iso = datetime.now().isoformat()
            # Select bookings where start_time >= now
            response = await client.table('bookings')\
                .select("*")\
                .eq('client_id', client_id)\
                .gte('start_time', now_iso)\
                .order('start_time', desc=False)\
                .limit(1)\
                .execute()
                
            if response.data:
                return response.data[0]
        except Exception as e:
            logger.error(f"❌ DB Error (get_upcoming_booking): {e}")
            
        return None

    async def delete_booking(self, booking_id: int) -> bool:
        """
        Deletes a booking from the database.
        """
        client = await self.get_client()
        if not client: return False
        
        try:
            await client.table('bookings').delete().eq('id', booking_id).execute()
            logger.info(f"🗑️ Booking {booking_id} deleted from DB.")
            return True
        except Exception as e:
            logger.error(f"❌ DB Error (delete_booking): {e}")
            return False

db_service = DBService()
