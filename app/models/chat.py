from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"

class MessageSource(str, Enum):
    internal = "internal"
    web = "web"

class AssistantType(str, Enum):
    typeX = "typeX"
    references = "references"
    academicReferences = "academicReferences"
    therapyGPT = "therapyGPT"
    whatsTrendy = "whatsTrendy"
    course = "course"

class ChatMode(str, Enum):
    gpt = "gpt"
    perplexity = "perplexity"

class MessageRequest(BaseModel):
    content: str
    role: MessageRole = MessageRole.user

class MessageResponse(BaseModel):
    id: str
    content: str
    role: MessageRole
    timestamp: datetime
    source: Optional[MessageSource] = None
    
    class Config:
        from_attributes = True

class ChatMessageRequest(BaseModel):
    message: str
    assistant_id: AssistantType
    mode: ChatMode = ChatMode.gpt
    chat_session_id: Optional[str] = None
    course_id: Optional[str] = None  # For course chats, pass the course_id

class ChatMessageResponse(BaseModel):
    message: MessageResponse
    chat_session_id: str
    assistant_id: AssistantType
    mode: ChatMode

class ChatSessionResponse(BaseModel):
    id: str
    user_id: str
    assistant_id: AssistantType
    created_at: datetime
    updated_at: datetime
    message_count: int
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class ChatHistoryResponse(BaseModel):
    session: ChatSessionResponse
    messages: List[MessageResponse]

