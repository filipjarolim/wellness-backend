from app.tools.definitions import ALL_TOOLS

def get_assistant_config():
    """
    Returns the Vapi assistant configuration.
    This separates the prompt/personality logic from the API handler.
    """
    return {
        "firstMessage": "Hello, doing great! Welcome to Smart Dental. How can I help you today?",
        "model": {
            "provider": "openai",
            "model": "gpt-4-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "You are Petra, a helpful receptionist at Smart Dental. You help customers book appointments. Check availability first before booking. Be polite and concise."
                }
            ],
            "tools": ALL_TOOLS
        },
        "voice": "jennifer-playht"
    }
