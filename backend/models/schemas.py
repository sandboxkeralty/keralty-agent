from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    role: str = "user"

class UserInDB(UserBase):
    user_id: str
    created_at: datetime
    updated_at: datetime

class SessionBase(BaseModel):
    title: str
    user_id: str

class SessionInDB(SessionBase):
    session_id: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MessageBase(BaseModel):
    session_id: str
    role: str # 'user' or 'agent'
    content: str

class MessageInDB(MessageBase):
    message_id: str
    timestamp: datetime
    agent_id: Optional[str] = None
    tools_used: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    feedback: Optional[str] = None

class AuditEvent(BaseModel):
    event_id: str
    user_email_hash: str
    action: str
    resource_type: str
    resource_id: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
