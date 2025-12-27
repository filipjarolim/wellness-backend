from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel

class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    day: str
    time: str
    service: str
    created_at: datetime = Field(default_factory=datetime.now)
