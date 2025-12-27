from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union, Literal

# --- Incoming Request Models ---

class VapiFunction(BaseModel):
    name: str
    arguments: Dict[str, Any]

class VapiToolCall(BaseModel):
    id: str
    type: str = "function"
    function: VapiFunction

class VapiMessageBase(BaseModel):
    # Base class is optional but good for shared fields. 
    # For discriminated union, the Literal in subclasses is key.
    pass

class VapiToolCallMessage(VapiMessageBase):
    type: Literal["tool-calls"] = "tool-calls"
    toolCalls: List[VapiToolCall]

class VapiAssistantRequestMessage(VapiMessageBase):
    type: Literal["assistant-request"] = "assistant-request"
    call: Optional[Dict[str, Any]] = None
    
class VapiEndOfCallReportMessage(VapiMessageBase):
    type: Literal["end-of-call-report"] = "end-of-call-report"
    # Add other fields if needed, e.g. analysis, transcript, etc.

class VapiHeader(BaseModel):
    pass

# Wrapper for the incoming JSON body from Vapi
class VapiWebhookPayload(BaseModel):
    message: Union[VapiToolCallMessage, VapiAssistantRequestMessage, VapiEndOfCallReportMessage] = Field(..., discriminator='type')


# --- Outgoing Response Models ---

class ToolCallResult(BaseModel):
    toolCallId: str
    result: str

class VapiToolCallResponse(BaseModel):
    results: List[ToolCallResult]

# For assistant-request response, we can define models or keep it dict-based 
# as it's a configuration object rather than data processing.
# But for consistency, let's define a basic wrapper.
class VapiAssistantResponse(BaseModel):
    assistant: Dict[str, Any]
