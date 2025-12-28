from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Booking(BaseModel):
    id: Optional[int] = Field(default=None) # We keep ID for compatibility but it's not a PK here
    name: str
    day: str
    time: str
    service: str
    created_at: datetime = Field(default_factory=datetime.now)
