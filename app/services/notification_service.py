import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from app.core.logger import logger
from app.core.config_loader import load_company_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Twilio Client
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Initialize Twilio Client globally if available
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Twilio Client: {e}")

def get_notification_config():
    """Laws notification config from company_config.json"""
    config = load_company_config()
    return config.get("notifications", {})

def send_sms(to_number: str, message: str) -> bool:
    """
    Sends an SMS using Twilio.
    Returns: True if successful, False otherwise.
    """
    config = get_notification_config()
    if not config.get("sms_enabled", False):
        logger.info("ℹ️ SMS notifications are disabled in config.")
        return False

    if not twilio_client:
        logger.error("❌ Twilio client is not initialized. Check .env variables.")
        return False
    
    if not TWILIO_PHONE_NUMBER:
        logger.error("❌ TWILIO_PHONE_NUMBER is missing in .env.")
        return False

    try:
        # Check if number starts with + and country code, generic handling or assume prepared
        # Twilio requires E.164 format (e.g., +1234567890)
        
        logger.info(f"📤 Sending SMS to {to_number}...")
        message = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )
        logger.info(f"✅ SMS odeslána na {to_number}: SID={message.sid}")
        return True
    except TwilioRestException as e:
        logger.error(f"❌ Chyba odeslání SMS (Twilio Error): {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Chyba odeslání SMS (Generic Error): {e}")
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
