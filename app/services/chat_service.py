import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.services.supabase_service import SupabaseService
from app.models.chat import (
    MessageRole, MessageSource, AssistantType, ChatMode,
    MessageResponse, ChatSessionResponse
)
import uuid

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        self.supabase = SupabaseService()
    
    def create_chat_session(
        self,
        user_id: str,
        assistant_id: AssistantType
    ) -> str:
        """Create a new chat session and return session ID"""
        logger.info(f"📝 Creating chat session - User: {user_id}, Assistant: {assistant_id}")
        logger.debug(f"   User ID type: {type(user_id)}, Assistant ID: {assistant_id.value}")
        
        try:
            session_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            logger.debug(f"   Generated session ID: {session_id}")
            logger.debug(f"   Timestamp: {now}")
            
            session_data = {
                "id": session_id,
                "user_id": user_id,
                "assistant_id": assistant_id.value,
                "created_at": now,
                "updated_at": now,
                "message_count": 0
            }
            logger.debug(f"   Session data: {session_data}")
            
            # Insert into chat_sessions table
            logger.debug(f"   Calling Supabase insert...")
            result = self.supabase.client.table("chat_sessions").insert(session_data).execute()
            logger.debug(f"   Supabase insert response: {result}")
            
            if not result.data:
                raise Exception("No data returned from Supabase insert")
            
            logger.info(f"✅ Chat session created: {session_id}")
            logger.debug(f"   Created session data: {result.data}")
            return session_id
            
        except Exception as e:
            error_msg = f"Failed to create chat session: {str(e)}"
            error_type = type(e).__name__
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Exception Type: {error_type}")
            logger.error(f"   User ID: {user_id}, Assistant: {assistant_id.value}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def save_message(
        self,
        session_id: str,
        content: str,
        role: MessageRole,
        source: Optional[MessageSource] = None
    ) -> MessageResponse:
        """Save a message to the database"""
        logger.info(f"💾 Saving message - Session: {session_id}, Role: {role}")
        logger.debug(f"   Content length: {len(content)} characters")
        logger.debug(f"   Source: {source.value if source else 'None'}")
        
        try:
            message_id = str(uuid.uuid4())
            now = datetime.utcnow()
            logger.debug(f"   Generated message ID: {message_id}")
            
            # Insert into messages table
            message_data = {
                "id": message_id,
                "chat_session_id": session_id,
                "content": content,
                "role": role.value,
                "timestamp": now.isoformat(),
                "source": source.value if source else None
            }
            logger.debug(f"   Message data prepared (content preview: {content[:50]}...)")
            
            logger.debug(f"   Step 1: Inserting message into database...")
            result = self.supabase.client.table("messages").insert(message_data).execute()
            logger.debug(f"   ✅ Message inserted: {result.data if result.data else 'No data returned'}")
            
            # Update session message count and updated_at
            logger.debug(f"   Step 2: Updating session message count...")
            session_data = self.supabase.client.table("chat_sessions").select("message_count").eq("id", session_id).execute()
            current_count = session_data.data[0]["message_count"] if session_data.data else 0
            logger.debug(f"   Current message count: {current_count}")
            
            update_data = {
                "message_count": current_count + 1,
                "updated_at": now.isoformat()
            }
            logger.debug(f"   Update data: {update_data}")
            
            update_result = self.supabase.client.table("chat_sessions").update(update_data).eq("id", session_id).execute()
            logger.debug(f"   ✅ Session updated: {update_result.data if update_result.data else 'No data returned'}")
            
            logger.info(f"✅ Message saved: {message_id}")
            
            return MessageResponse(
                id=message_id,
                content=content,
                role=role,
                timestamp=now,
                source=source
            )
            
        except Exception as e:
            error_msg = f"Failed to save message: {str(e)}"
            error_type = type(e).__name__
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Exception Type: {error_type}")
            logger.error(f"   Session ID: {session_id}, Role: {role.value}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def get_chat_history(
        self,
        session_id: str,
        user_id: str
    ) -> List[MessageResponse]:
        """Get all messages for a chat session"""
        logger.info(f"📖 Fetching chat history - Session: {session_id}")
        
        try:
            # Verify session belongs to user
            session = self.supabase.client.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
            
            if not session.data:
                raise Exception("Chat session not found or access denied")
            
            # Get messages
            messages = self.supabase.client.table("messages").select("*").eq("chat_session_id", session_id).order("timestamp", desc=False).execute()
            
            message_list = []
            for msg in messages.data:
                message_list.append(MessageResponse(
                    id=msg["id"],
                    content=msg["content"],
                    role=MessageRole(msg["role"]),
                    timestamp=datetime.fromisoformat(msg["timestamp"].replace('Z', '+00:00')),
                    source=MessageSource(msg["source"]) if msg["source"] else None
                ))
            
            logger.info(f"✅ Retrieved {len(message_list)} messages for session: {session_id}")
            return message_list
            
        except Exception as e:
            error_msg = f"Failed to get chat history: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def update_session_openai_ids(
        self,
        session_id: str,
        openai_assistant_id: Optional[str] = None,
        openai_thread_id: Optional[str] = None
    ) -> bool:
        """Update chat session with OpenAI assistant_id and thread_id"""
        logger.info(f"📝 Updating session OpenAI IDs - Session: {session_id}")
        try:
            update_data = {}
            if openai_assistant_id:
                update_data["openai_assistant_id"] = openai_assistant_id
            if openai_thread_id:
                update_data["openai_thread_id"] = openai_thread_id
            
            if update_data:
                result = self.supabase.client.table("chat_sessions").update(update_data).eq("id", session_id).execute()
                logger.info(f"   ✅ Session updated with OpenAI IDs")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Failed to update session OpenAI IDs: {str(e)}")
            return False
    
    def get_session_openai_ids(self, session_id: str) -> Dict[str, Optional[str]]:
        """Get OpenAI assistant_id and thread_id from session"""
        logger.debug(f"📖 Getting OpenAI IDs for session: {session_id}")
        try:
            session = self.supabase.client.table("chat_sessions").select("openai_assistant_id, openai_thread_id").eq("id", session_id).execute()
            
            if session.data and len(session.data) > 0:
                return {
                    "assistant_id": session.data[0].get("openai_assistant_id"),
                    "thread_id": session.data[0].get("openai_thread_id")
                }
            return {"assistant_id": None, "thread_id": None}
        except Exception as e:
            logger.warning(f"   ⚠️  Could not get OpenAI IDs: {str(e)}")
            return {"assistant_id": None, "thread_id": None}
    
    def get_user_sessions(
        self,
        user_id: str
    ) -> List[ChatSessionResponse]:
        """Get all chat sessions for a user, including course information"""
        logger.info(f"📋 Fetching user sessions - User: {user_id}")
        
        try:
            # Get all sessions first
            sessions = self.supabase.client.table("chat_sessions").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
            
            session_list = []
            course_ids = []
            
            # Collect course IDs
            for sess in sessions.data:
                if sess.get("course_id"):
                    course_ids.append(sess["course_id"])
            
            # Fetch course names in batch if needed
            course_names_map = {}
            if course_ids:
                try:
                    courses = self.supabase.client.table("courses").select("id, name").in_("id", course_ids).execute()
                    if courses.data:
                        for course in courses.data:
                            course_names_map[course["id"]] = course["name"]
                except Exception as e:
                    logger.warning(f"⚠️  Failed to fetch course names: {str(e)}")
            
            # Build session list with course names
            for sess in sessions.data:
                course_id = sess.get("course_id")
                course_name = course_names_map.get(course_id) if course_id else None
                
                session_list.append(ChatSessionResponse(
                    id=sess["id"],
                    user_id=sess["user_id"],
                    assistant_id=AssistantType(sess["assistant_id"]),
                    created_at=datetime.fromisoformat(sess["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(sess["updated_at"].replace('Z', '+00:00')),
                    message_count=sess["message_count"],
                    course_id=course_id,
                    course_name=course_name
                ))
            
            logger.info(f"✅ Retrieved {len(session_list)} sessions for user: {user_id}")
            return session_list
            
        except Exception as e:
            error_msg = f"Failed to get user sessions: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def delete_chat_session(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """Delete a chat session and all its messages"""
        logger.info(f"🗑️  Deleting chat session - Session: {session_id}, User: {user_id}")
        
        try:
            # Verify session belongs to user
            session = self.supabase.client.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
            
            if not session.data:
                raise Exception("Chat session not found or access denied")
            
            # Delete messages first
            self.supabase.client.table("messages").delete().eq("chat_session_id", session_id).execute()
            
            # Delete session
            self.supabase.client.table("chat_sessions").delete().eq("id", session_id).execute()
            
            logger.info(f"✅ Chat session deleted: {session_id}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete chat session: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)

