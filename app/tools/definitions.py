# Tool definitions for Vapi/LLM function calling

CHECK_AVAILABILITY_TOOL = {
    "type": "function",
    "function": {
        "name": "check_availability",
        "description": "Check if there are open slots for an appointment on a specific date.",
        "parameters": {
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "description": "The day to check availability for, in ISO 8601 format YYYY-MM-DD (e.g., '2024-05-20')."
                },
                "time": {
                    "type": "string",
                    "description": "The specific time to check in HH:MM format (e.g., '14:00')."
                }
            },
            "required": ["day", "time"]
        }
    }
}

BOOK_APPOINTMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "book_appointment",
        "description": "Book a specific time slot for an appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "description": "The day of the appointment in ISO 8601 format YYYY-MM-DD."
                },
                "time": {
                    "type": "string",
                    "description": "The time of the appointment (e.g., '14:00')."
                },
                "name": {
                    "type": "string",
                    "description": "The name of the customer."
                },
                "service": {
                    "type": "string",
                    "description": "The service requested (e.g. 'dental checkup')."
                }
            },
            "required": ["day", "time", "name"]
        }
    }
}

ALL_TOOLS = [CHECK_AVAILABILITY_TOOL, BOOK_APPOINTMENT_TOOL]
