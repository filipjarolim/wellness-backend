from fastapi import APIRouter, Request, HTTPException, Depends
import logging
from typing import Union
from sqlmodel import Session

# New Models and Service
from app.models.vapi_models import (
    VapiWebhookPayload, 
    VapiToolCallMessage, 
    VapiAssistantRequestMessage, 
    VapiToolCallResponse, 
    ToolCallResult,
    VapiAssistantResponse
)
from app.services.booking_service import BookingService
from app.services.llm_service import get_assistant_config
from app.core.database import get_session

router = APIRouter()
logger = logging.getLogger("uvicorn")

@router.post("/webhook")
async def vapi_webhook(
    payload: VapiWebhookPayload, 
    session: Session = Depends(get_session)
) -> Union[VapiAssistantResponse, VapiToolCallResponse, dict]:
    """
    Handle incoming webhooks from Vapi.ai with strict Pydantic validation.
    """
    logger.info(f"Received Vapi Payload: {payload.model_dump()}")
    
    # Instantiate service with session
    booking_service = BookingService(session)
    
    # payload.message is a discriminated union, so we check the type
    message = payload.message
    
    if message.type == "assistant-request":
        # Handshake
        logger.info("Handling assistant-request")
        return VapiAssistantResponse(assistant=get_assistant_config())
        
    elif message.type == "tool-calls":
        # Function Calling
        logger.info("Handling tool-calls")
        # message is guaranteed to be VapiToolCallMessage by Pydantic if type matches
        if isinstance(message, VapiToolCallMessage):
            results = []
            
            for tool_call in message.toolCalls:
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
                call_id = tool_call.id
                
                result_content = "Error: Function not found"
                
                if function_name == "check_availability":
                    day = arguments.get("day")
                    time = arguments.get("time")
                    result_content = booking_service.check_availability(day, time) # Removed await as it's sync now in this implementation or should be async?
                    # Note: SQLModel sync session usage in async endpoint is OK for simple apps, 
                    # but technically blocking. For now we use sync methods in BookingService as per previous step which used sync session methods.
                    # Wait, create_booking uses sync session commmit.
                    # Let's check BookingService definition in previous step. yes it is regular def check_availability.
                    # So no await needed.
                    
                elif function_name == "book_appointment":
                    day = arguments.get("day")
                    time = arguments.get("time")
                    name = arguments.get("name")
                    service = arguments.get("service", "General Service")
                    resp = booking_service.book_appointment(day, time, name, service) # Removed await
                    result_content = resp.get("message", "Booking failed")
                
                results.append(ToolCallResult(toolCallId=call_id, result=result_content))
                
            return VapiToolCallResponse(results=results)
            
    elif message.type == "end-of-call-report":
        logger.info("Call ended.")
        return {}
        
    return {}
