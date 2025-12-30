# test_notifikaci.py
from app.services.notification_service import send_sms, send_email

# Tvoje číslo (kam má přijít testovací SMS)
TEST_PHONE = "+420605017322"  # Doplň svoje číslo!
# Tvůj email (kam má přijít testovací email)
TEST_EMAIL = "jarolimfilip07@gmail.com"

print("--- ZAČÍNÁM TEST ---")

# 1. Test SMS
print(f"📡 Zkouším poslat SMS na {TEST_PHONE}...")
try:
    sid = send_sms(TEST_PHONE, "Test z Barber Shopu! Pokud toto čteš, Twilio funguje. 🚀")
    if sid:
        print(f"✅ SMS Úspěch! SID: {sid}")
    else:
        print("⚠️ SMS funkce proběhla, ale nevrátila ID (možná je vypnutá v configu?)")
except Exception as e:
    print(f"❌ CHYBA SMS: {e}")

# 2. Test Email
print(f"📧 Zkouším poslat Email na {TEST_EMAIL}...")
try:
    send_email("Test Notifikací", "Ahoj, toto je testovací email z tvého Python backendu.\n\nFunguje to!")
    print("✅ Email odeslán bez chyby.")
except Exception as e:
    print(f"❌ CHYBA EMAIL: {e}")

print("--- KONEC TESTU ---")