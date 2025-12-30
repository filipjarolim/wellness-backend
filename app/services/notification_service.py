import os
import smtplib
import requests
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.logger import logger
from app.core.config_loader import load_company_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GoSMS Configuration
GOSMS_CLIENT_ID = os.getenv("GOSMS_CLIENT_ID")
GOSMS_CLIENT_SECRET = os.getenv("GOSMS_CLIENT_SECRET")
GOSMS_CHANNEL_ID = os.getenv("GOSMS_CHANNEL_ID")

# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Helper for caching GoSMS token
_gosms_token = None
_gosms_token_expires_at = 0

def get_notification_config():
    """Laws notification config from company_config.json"""
    config = load_company_config()
    return config.get("notifications", {})

def _get_gosms_token() -> str:
    """
    Retrieves or refreshes OAuth2 access_token for GoSMS.
    """
    global _gosms_token, _gosms_token_expires_at
    
    # Check if token is valid (with 60sec buffer)
    if _gosms_token and time.time() < _gosms_token_expires_at - 60:
        return _gosms_token
    
    if not GOSMS_CLIENT_ID or not GOSMS_CLIENT_SECRET:
         logger.error("❌ GoSMS Credentials missing (GOSMS_CLIENT_ID or GOSMS_CLIENT_SECRET).")
         return None

    url = "https://app.gosms.cz/oauth/v2/token"
    payload = {
        "client_id": GOSMS_CLIENT_ID,
        "client_secret": GOSMS_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        _gosms_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        _gosms_token_expires_at = time.time() + expires_in
        
        logger.info(f"🔑 GoSMS Token obtained (expires in {expires_in}s)")
        return _gosms_token
    except Exception as e:
        logger.error(f"❌ Failed to get GoSMS token: {e}")
        return None

def send_sms(to_number: str, message: str) -> bool:
    """
    Sends an SMS using GoSMS API.
    Returns: True if successful, False otherwise.
    """
    config = get_notification_config()
    if not config.get("sms_enabled", False):
        logger.info("ℹ️ SMS notifications are disabled in config.")
        return False
    
    if not GOSMS_CHANNEL_ID:
        logger.error("❌ GOSMS_CHANNEL_ID is missing in .env.")
        return False
        
    token = _get_gosms_token()
    if not token:
        return False

    # Clean phone number (remove spaces)
    clean_number = to_number.replace(" ", "").strip()
    
    url = "https://app.gosms.cz/api/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Convert channel ID to int if possible, API might expect int
    try:
         channel_id = int(GOSMS_CHANNEL_ID)
    except ValueError:
         channel_id = GOSMS_CHANNEL_ID # fallback to string if fails

    payload = {
        "message": message,
        "recipients": [clean_number],
        "channel": channel_id
    }
    
    try:
        logger.info(f"📤 Sending SMS to {clean_number} via GoSMS...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 201 or response.status_code == 200:
             logger.info(f"✅ SMS successfully sent to {clean_number}.")
             return True
        else:
             logger.error(f"❌ GoSMS Error {response.status_code}: {response.text}")
             return False
             
    except Exception as e:
        logger.error(f"❌ Exception sending SMS via GoSMS: {e}")
        return False

def send_email(subject: str, body: str, to_email: str = None) -> bool:
    """
    Sends an email using SMTP (e.g., Gmail).
    defaults `to_email` to the owner_email from config if not provided.
    Returns: True if successful, False otherwise.
    """
    config = load_company_config()
    notif_config = config.get("notifications", {})
    
    if not notif_config.get("email_enabled", False):
         logger.info("ℹ️ Email notifications are disabled in config.")
         return False

    if not to_email:
        to_email = config.get("owner_email")
        if not to_email:
             logger.error("❌ No recipient email found (owner_email missing in config).")
             return False

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.error("❌ SMTP credentials missing in .env.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_USERNAME, to_email, text)
        server.quit()
        
        logger.info(f"✅ Email odeslán na {to_email} with subject: '{subject}'")
        return True
    except Exception as e:
        logger.error(f"❌ Chyba odeslání Emailu: {e}")
        return False
