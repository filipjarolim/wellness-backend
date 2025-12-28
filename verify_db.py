from app.services.booking_service import BookingService
import logging

# Mock session
class MockSession:
    def add(self, *args, **kwargs): pass
    def commit(self, *args, **kwargs): pass
    def refresh(self, *args, **kwargs): pass

logging.basicConfig(level=logging.INFO)

def test_customer_db():
    print("Testing Customer DB...")
    service = BookingService(session=MockSession())
    
    # Test Save
    phone = "123456789"
    name = "Test User"
    service.save_customer(phone, name)
    
    # Test Get
    retrieved_name = service.get_caller_name(phone)
    if retrieved_name == name:
        print(f"✅ Success: Retrieved {retrieved_name} for {phone}")
    else:
        print(f"❌ Failed: Expected {name}, got {retrieved_name}")

if __name__ == "__main__":
    test_customer_db()
