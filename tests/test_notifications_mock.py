import pytest
from unittest.mock import MagicMock, patch
from app.services.notification_service import send_sms, send_email

# Test SMS (Mocked)
@patch("app.services.notification_service.requests.post")
@patch("app.services.notification_service.GOSMS_CHANNEL_ID", "123") # Ensure ID exists
@patch("app.services.notification_service.GOSMS_CLIENT_ID", "mock_id")
@patch("app.services.notification_service.GOSMS_CLIENT_SECRET", "mock_secret")
def test_send_sms_mocked(mock_post):
    # Mock Token Response
    mock_response_token = MagicMock()
    mock_response_token.status_code = 200
    mock_response_token.json.return_value = {"access_token": "fake_token", "expires_in": 3600}
    
    # Mock Message Response
    mock_response_msg = MagicMock()
    mock_response_msg.status_code = 201
    
    # We need to handle multiple calls to post:
    # 1. Token (if not cached) -> returns token
    # 2. Message -> returns status
    
    # Using side_effect to return different responses
    mock_post.side_effect = [mock_response_token, mock_response_msg]
    
    # Force token refresh logic if needed, but since it's global variable in module, 
    # we might need to reset it or patch `_get_gosms_token` directly.
    # Simpler: Patch `_get_gosms_token` to return "fake_token" directly so we skip the first request.
    
    with patch("app.services.notification_service._get_gosms_token", return_value="fake_token"):
        # Reset side_effect because we skipped token call
        mock_post.side_effect = None
        mock_post.return_value = mock_response_msg
        
        # Enable SMS in config
        with patch("app.services.notification_service.get_notification_config", return_value={"sms_enabled": True}):
            result = send_sms("+420123456789", "Test Message")
            
            assert result is True
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "api/v1/messages" in args[0]
            assert kwargs['json']['message'] == "Test Message"
            assert kwargs['json']['recipients'] == ["+420123456789"]

# Test Email (Mocked)
@patch("app.services.notification_service.smtplib.SMTP")
def test_send_email_mocked(mock_smtp_cls):
    # Setup Mock
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server
    
    with patch("app.services.notification_service.load_company_config") as mock_config:
        # Mock Config to enable email and have credentials
        mock_config.return_value = {
            "email_enabled": True, # This comes from notif config, check impl
            "notifications": {"email_enabled": True}, 
            "owner_email": "owner@test.com"
        }
        
        # Need to ensure SMTP creds are mocked too if they are read from env at module level?
        # They are read at module level: SMTP_USERNAME = os.getenv...
        # So we patch the module variables.
        with patch("app.services.notification_service.SMTP_USERNAME", "user"), \
             patch("app.services.notification_service.SMTP_PASSWORD", "pass"):
            
             result = send_email("Test Subject", "Test Body", "client@test.com")
             
             assert result is True
             mock_smtp_cls.assert_called_once()
             mock_server.starttls.assert_called_once()
             mock_server.login.assert_called_with("user", "pass")
             mock_server.sendmail.assert_called_once()
