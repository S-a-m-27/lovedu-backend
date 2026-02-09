import os
import logging
import io
import time
import asyncio
import re
from openai import OpenAI
from typing import Optional, Dict, Any, List
from app.models.chat import AssistantType, ChatMode, MessageSource

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def _assistant_env_suffix(assistant_id: AssistantType) -> str:
    """
    Convert AssistantType values (camelCase / mixed) into ENV-friendly names.

    Examples:
      typeX -> TYPEX
      references -> REFERENCES
      academicReferences -> ACADEMIC_REFERENCES
      therapyGPT -> THERAPY_GPT
      whatsTrendy -> WHATS_TRENDY
      course -> COURSE
    """
    raw = assistant_id.value if hasattr(assistant_id, "value") else str(assistant_id)
    # Special-case to match existing env keys
    if raw == "typeX":
        return "TYPEX"
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", raw)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).upper()
    return snake

def _normalize_prompt_text(text: str) -> str:
    """
    Support multi-line prompts stored in .env by letting users write literal '\\n'.
    """
    return text.replace("\\n", "\n").strip()

def _load_prompt_from_env_or_file(key: str) -> str:
    """
    Loads prompt from:
      - {key} (inline env var)
      - {key}_PATH (file path env var; relative to backend/ or absolute)

    Returns a normalized string (supports '\\n' -> newlines).
    """
    inline = os.getenv(key)
    if inline and inline.strip():
        normalized = _normalize_prompt_text(inline)
        logger.info(f"🧩 Prompt source: {key} (inline env)")
        logger.debug(f"   {key} length: {len(normalized)} chars")
        return normalized

    path_key = f"{key}_PATH"
    path_val = (os.getenv(path_key) or "").strip()
    if not path_val:
        logger.warning(f"⚠️ Prompt not found: {key} and {path_key} are empty")
        return ""

    path = path_val
    if not os.path.isabs(path):
        path = os.path.join(BACKEND_DIR, path)

    logger.info(f"🧩 Prompt source: {path_key} (file)")
    logger.debug(f"   {path_key} resolved path: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            logger.debug(f"   {path_key} length: {len(content)} chars")
            return content
    except FileNotFoundError:
        logger.error(f"❌ Prompt file not found for {path_key}: {path}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to read prompt file for {path_key}: {path} - {str(e)}")
        raise

class OpenAIService:
    _instance: Optional['OpenAIService'] = None
    _client: Optional[OpenAI] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenAIService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            logger.info("🔧 Initializing OpenAIService...")
            
            api_key = os.getenv("OPENAI_API_KEY")
            
            if api_key:
                masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
                logger.info(f"📋 OPENAI_API_KEY: {masked_key} (loaded)")
            else:
                logger.error("❌ OPENAI_API_KEY: NOT SET")
            
            if not api_key:
                error_msg = "OPENAI_API_KEY must be set"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            try:
                self._client = OpenAI(api_key=api_key)
                logger.info("✅ OpenAI client created successfully")
            except Exception as e:
                logger.error(f"❌ Failed to create OpenAI client: {str(e)}")
                raise
    
    @property
    def client(self) -> OpenAI:
        return self._client
    
    def get_assistant_system_prompt(self, assistant_id: AssistantType) -> str:
        """
        Load the assistant system prompt from environment variables.

        Supported configuration:
          - Inline env var:        AGENT_PROMPT_<ASSISTANT>
          - File path env var:     AGENT_PROMPT_<ASSISTANT>_PATH

        Optional global prefix applied to all assistants:
          - Inline env var:        AGENT_PROMPT_BASE
          - File path env var:     AGENT_PROMPT_BASE_PATH

        Assistants (derived from AssistantType values):
          - TYPEX
          - REFERENCES
          - ACADEMIC_REFERENCES
          - THERAPY_GPT
          - WHATS_TRENDY
          - COURSE
        """
        suffix = _assistant_env_suffix(assistant_id)
        prompt_key = f"AGENT_PROMPT_{suffix}"
        logger.info(f"🧩 Loading prompt for assistant: {assistant_id} (env suffix: {suffix})")

        base_prompt = _load_prompt_from_env_or_file("AGENT_PROMPT_BASE")
        prompt = _load_prompt_from_env_or_file(prompt_key)

        logger.debug(f"   Base prompt present: {'yes' if base_prompt else 'no'}")
        logger.debug(f"   Assistant prompt present: {'yes' if prompt else 'no'}")

        if not prompt:
            logger.error(f"❌ Missing/empty agent prompt: {prompt_key} (or {prompt_key}_PATH)")
            raise ValueError(f"Missing/empty environment variable: {prompt_key}")

        full = f"{base_prompt}\n\n{prompt}" if base_prompt else prompt
        logger.info(f"🧩 Loaded agent prompt: {prompt_key} (len={len(full)})")
        return full
    async def generate_chat_response(
        self,
        message: str,
        assistant_id: AssistantType,
        mode: ChatMode,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        course_id: Optional[str] = None,
        course_name: Optional[str] = None,
        course_files: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Generate chat response using OpenAI
        Returns: {content: str, source: MessageSource}
        """
        logger.info(f"🤖 Generating chat response - Assistant: {assistant_id}, Mode: {mode}")
        if course_id:
            logger.info(f"   📚 Course-specific chat - Course: {course_name} (ID: {course_id})")
        logger.debug(f"   User message: {message[:100]}...")
        logger.debug(f"   Conversation history length: {len(conversation_history) if conversation_history else 0}")
        
        try:
            system_prompt = self.get_assistant_system_prompt(assistant_id)
            
            # Enhance system prompt for course-specific chats
            if course_id and course_name:
                course_context = f"\n\nIMPORTANT: This is a course-specific chat for '{course_name}' (Course ID: {course_id}). "
                if course_files and len(course_files) > 0:
                    file_names = [f.file_name for f in course_files]
                    course_context += f"You have access to the following course materials: {', '.join(file_names)}. "
                course_context += "You MUST ONLY answer questions based on the content from these specific course materials. "
                course_context += "If asked about topics not covered in the course materials, politely explain that you can only answer questions related to this specific course content."
                system_prompt = course_context + system_prompt
                logger.debug(f"   📚 Course context added to system prompt")
            
            logger.debug(f"   System prompt length: {len(system_prompt)} characters")
            
            # Build messages array
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if provided
            if conversation_history:
                logger.debug(f"   Adding {len(conversation_history)} messages from history")
                messages.extend(conversation_history)
            else:
                logger.debug("   No conversation history provided - starting new conversation")
            
            # Add current user message
            messages.append({"role": "user", "content": message})
            
            logger.debug(f"📤 Sending request to OpenAI with {len(messages)} total messages")
            logger.debug(f"   Model: {'gpt-4' if mode == ChatMode.gpt else 'gpt-3.5-turbo'}")
            
            # Call OpenAI API
            response = self._client.chat.completions.create(
                model="gpt-4" if mode == ChatMode.gpt else "gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message.content
            source = MessageSource.internal if mode == ChatMode.gpt else MessageSource.web
            
            logger.info(f"✅ OpenAI response generated successfully (Mode: {mode})")
            logger.debug(f"   Response length: {len(assistant_message)} characters")
            logger.debug(f"   Response preview: {assistant_message[:100]}...")
            
            return {
                "content": assistant_message,
                "source": source
            }
            
        except Exception as e:
            error_msg = f"OpenAI API error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Assistant: {assistant_id}, Mode: {mode}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    async def upload_file_to_openai(self, file_content: bytes, file_name: str) -> str:
        """
        Upload a PDF file to OpenAI and return the file_id
        Returns: OpenAI file_id
        """
        logger.info(f"📤 Uploading file to OpenAI: {file_name}")
        try:
            # Create a file-like object from bytes
            file_obj = io.BytesIO(file_content)
            file_obj.name = file_name
            
            # Upload to OpenAI with 'assistants' purpose
            file_response = self._client.files.create(
                file=file_obj,
                purpose="assistants"
            )
            
            file_id = file_response.id
            logger.info(f"   ✅ File uploaded to OpenAI - ID: {file_id}")
            
            # Wait for file to be processed (required for assistants)
            logger.debug(f"   ⏳ Waiting for file processing...")
            while True:
                file_status = self._client.files.retrieve(file_id)
                if file_status.status == "processed":
                    logger.debug(f"   ✅ File processed successfully")
                    break
                elif file_status.status == "error":
                    raise Exception(f"File processing failed: {file_status.error}")
                time.sleep(1)
            
            return file_id
            
        except Exception as e:
            logger.error(f"❌ Failed to upload file to OpenAI: {str(e)}")
            raise Exception(f"Failed to upload file to OpenAI: {str(e)}")
    
    async def get_or_create_course_assistant(
        self,
        course_id: str,
        course_name: str,
        file_ids: List[str]
    ) -> str:
        """
        Get or create an OpenAI Assistant for a course with attached files
        Returns: assistant_id
        """
        logger.info(f"🤖 Getting/creating assistant for course: {course_name}")
        
        try:
            # For now, we'll create a new assistant each time
            # In production, you might want to store assistant_id in database and reuse it
            system_prompt = self.get_assistant_system_prompt(AssistantType.course)
            course_context = (
                f"IMPORTANT: This is a course-specific assistant for '{course_name}' (Course ID: {course_id}). "
                f"You have access to course materials through attached files. "
                f"Answer questions based ONLY on the content from these files. "
                f"If asked about topics not in the files, politely explain you can only answer based on the course materials.\n\n"
            )
            full_prompt = course_context + system_prompt
            
            # In OpenAI SDK 2.x, vector_stores API is not available in beta object
            # We need to create vector stores via REST API directly
            vector_store_id = None
            if file_ids:
                logger.info(f"   📁 Creating vector store with {len(file_ids)} files via REST API...")
                
                try:
                    # Use httpx to make direct REST API call to create vector store
                    import httpx
                    
                    api_key = os.getenv("OPENAI_API_KEY")
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "OpenAI-Beta": "assistants=v2"
                    }
                    
                    # Create vector store via REST API
                    vector_store_data = {
                        "name": f"Course Materials: {course_name}",
                        "file_ids": file_ids
                    }
                    
                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.post(
                            "https://api.openai.com/v1/vector_stores",
                            headers=headers,
                            json=vector_store_data,
                            timeout=60.0
                        )
                        response.raise_for_status()
                        vector_store_result = response.json()
                        vector_store_id = vector_store_result["id"]
                        logger.info(f"   ✅ Vector store created via REST API - ID: {vector_store_id}")
                        
                        # Wait for vector store to be ready
                        logger.debug(f"   ⏳ Waiting for vector store to be ready...")
                        max_wait_time = 60
                        wait_time = 0
                        while wait_time < max_wait_time:
                            status_response = await http_client.get(
                                f"https://api.openai.com/v1/vector_stores/{vector_store_id}",
                                headers=headers,
                                timeout=30.0
                            )
                            status_response.raise_for_status()
                            status_data = status_response.json()
                            
                            if status_data.get("status") == "completed":
                                logger.debug(f"   ✅ Vector store ready")
                                break
                            elif status_data.get("status") == "failed":
                                raise Exception(f"Vector store creation failed")
                            await asyncio.sleep(2)
                            wait_time += 2
                        
                        if wait_time >= max_wait_time:
                            logger.warning(f"   ⚠️  Vector store not ready after {max_wait_time}s, proceeding anyway")
                            
                except Exception as e:
                    logger.error(f"   ❌ Failed to create vector store via REST API: {str(e)}")
                    raise Exception(f"Failed to create vector store: {str(e)}")
            
            # Create assistant with file_search tool enabled
            # Use vector_store_id in tool_resources (the correct API format)
            assistant_params = {
                "name": f"Course Assistant: {course_name}",
                "instructions": full_prompt,
                "model": "gpt-4-turbo-preview",  # Use gpt-4-turbo-preview for file search
            }
            
            if file_ids and vector_store_id:
                logger.info(f"   📎 Creating assistant with file_search tool and vector store...")
                assistant_params["tools"] = [{"type": "file_search"}]
                assistant_params["tool_resources"] = {
                    "file_search": {
                        "vector_store_ids": [vector_store_id]  # Correct API format
                    }
                }
            elif file_ids:
                logger.warning(f"   ⚠️  No vector store ID available, creating assistant without file attachment")
            
            logger.info(f"   📎 Creating assistant...")
            assistant = self._client.beta.assistants.create(**assistant_params)
            
            # Verify the assistant was created with files
            if file_ids:
                try:
                    retrieved_assistant = self._client.beta.assistants.retrieve(assistant.id)
                    if hasattr(retrieved_assistant, 'tool_resources') and retrieved_assistant.tool_resources:
                        if hasattr(retrieved_assistant.tool_resources, 'file_search'):
                            file_search = retrieved_assistant.tool_resources.file_search
                            if hasattr(file_search, 'vector_store_ids') and file_search.vector_store_ids:
                                logger.info(f"   ✅ Vector store created automatically - IDs: {file_search.vector_store_ids}")
                            else:
                                logger.info(f"   ✅ Assistant created with file_search tool (files attached)")
                        else:
                            logger.warning(f"   ⚠️  File search not found in tool resources")
                    else:
                        logger.warning(f"   ⚠️  Tool resources not found")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not verify assistant configuration: {str(e)}")
                    logger.info(f"   ℹ️  Assistant created - verification failed but may still work")
            
            assistant_id = assistant.id
            logger.info(f"   ✅ Assistant created - ID: {assistant_id}")
            
            return assistant_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create assistant: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Failed to create assistant: {str(e)}")
    
    async def get_or_create_agent_assistant(
        self,
        assistant_id: AssistantType,
        file_ids: List[str]
    ) -> str:
        """
        Get or create an OpenAI Assistant for a non-course agent with attached files
        Returns: assistant_id
        """
        logger.info(f"🤖 Getting/creating assistant for agent: {assistant_id.value}")
        
        try:
            system_prompt = self.get_assistant_system_prompt(assistant_id)
            
            # Create vector store if we have files
            vector_store_id = None
            if file_ids:
                logger.info(f"   📁 Creating vector store with {len(file_ids)} files via REST API...")
                
                try:
                    # Use httpx to make direct REST API call to create vector store
                    import httpx
                    import asyncio
                    
                    api_key = os.getenv("OPENAI_API_KEY")
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "OpenAI-Beta": "assistants=v2"
                    }
                    
                    # Create vector store via REST API
                    vector_store_data = {
                        "name": f"Agent Files: {assistant_id.value}",
                        "file_ids": file_ids
                    }
                    
                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.post(
                            "https://api.openai.com/v1/vector_stores",
                            headers=headers,
                            json=vector_store_data,
                            timeout=60.0
                        )
                        response.raise_for_status()
                        vector_store_result = response.json()
                        vector_store_id = vector_store_result["id"]
                        logger.info(f"   ✅ Vector store created via REST API - ID: {vector_store_id}")
                        
                        # Wait for vector store to be ready
                        logger.debug(f"   ⏳ Waiting for vector store to be ready...")
                        max_wait_time = 60
                        wait_time = 0
                        while wait_time < max_wait_time:
                            status_response = await http_client.get(
                                f"https://api.openai.com/v1/vector_stores/{vector_store_id}",
                                headers=headers,
                                timeout=30.0
                            )
                            status_response.raise_for_status()
                            status_data = status_response.json()
                            
                            if status_data.get("status") == "completed":
                                logger.debug(f"   ✅ Vector store ready")
                                break
                            elif status_data.get("status") == "failed":
                                raise Exception(f"Vector store creation failed")
                            await asyncio.sleep(2)
                            wait_time += 2
                        
                        if wait_time >= max_wait_time:
                            logger.warning(f"   ⚠️  Vector store not ready after {max_wait_time}s, proceeding anyway")
                            
                except Exception as e:
                    logger.error(f"   ❌ Failed to create vector store via REST API: {str(e)}")
                    raise Exception(f"Failed to create vector store: {str(e)}")
            
            # Create assistant
            assistant_params = {
                "name": f"Agent Assistant - {assistant_id.value}",
                "instructions": system_prompt,
                "model": "gpt-4-turbo-preview",
            }
            
            if file_ids and vector_store_id:
                logger.info(f"   📎 Creating assistant with file_search tool and vector store...")
                assistant_params["tools"] = [{"type": "file_search"}]
                assistant_params["tool_resources"] = {
                    "file_search": {
                        "vector_store_ids": [vector_store_id]
                    }
                }
            elif file_ids:
                logger.warning(f"   ⚠️  No vector store ID available, creating assistant without file attachment")
            
            logger.info(f"   📎 Creating assistant...")
            assistant = self._client.beta.assistants.create(**assistant_params)
            
            # Verify the assistant was created with files
            if file_ids:
                try:
                    retrieved_assistant = self._client.beta.assistants.retrieve(assistant.id)
                    if hasattr(retrieved_assistant, 'tool_resources') and retrieved_assistant.tool_resources:
                        if hasattr(retrieved_assistant.tool_resources, 'file_search'):
                            file_search = retrieved_assistant.tool_resources.file_search
                            if hasattr(file_search, 'vector_store_ids') and file_search.vector_store_ids:
                                logger.info(f"   ✅ Vector store created automatically - IDs: {file_search.vector_store_ids}")
                            else:
                                logger.info(f"   ✅ Assistant created with file_search tool (files attached)")
                        else:
                            logger.warning(f"   ⚠️  File search not found in tool resources")
                    else:
                        logger.warning(f"   ⚠️  Tool resources not found")
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not verify assistant configuration: {str(e)}")
                    logger.info(f"   ℹ️  Assistant created - verification failed but may still work")
            
            assistant_openai_id = assistant.id
            logger.info(f"   ✅ Assistant created - ID: {assistant_openai_id}")
            
            return assistant_openai_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create assistant: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Failed to create assistant: {str(e)}")
    
    async def get_or_create_thread(self, thread_id: Optional[str] = None) -> tuple[str, bool]:
        """
        Get existing thread or create a new one
        Returns: (thread_id, is_new_thread)
        """
        if thread_id:
            try:
                # Verify thread exists
                self._client.beta.threads.retrieve(thread_id)
                logger.debug(f"   ✅ Using existing thread - ID: {thread_id}")
                return (thread_id, False)  # Existing thread
            except Exception as e:
                logger.warning(f"   ⚠️  Thread not found, creating new one: {str(e)}")
        
        # Create new thread
        logger.info("   📝 Creating new thread...")
        thread = self._client.beta.threads.create()
        logger.info(f"   ✅ Thread created - ID: {thread.id}")
        return (thread.id, True)  # New thread
    
    async def add_message_to_thread(
        self,
        thread_id: str,
        role: str,
        content: str
    ) -> None:
        """Add a message to a thread"""
        try:
            self._client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=content
            )
            logger.debug(f"   ✅ Message added to thread")
        except Exception as e:
            logger.error(f"❌ Failed to add message to thread: {str(e)}")
            raise
    
    async def generate_chat_response_with_assistants_api(
        self,
        message: str,
        assistant_id: str,
        thread_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate chat response using OpenAI Assistants API
        Returns: {content: str, source: MessageSource, thread_id: str}
        """
        logger.info(f"🤖 Generating response with Assistants API - Assistant: {assistant_id}")
        
        try:
            # Get or create thread (returns thread_id and is_new flag)
            thread_id, is_new_thread = await self.get_or_create_thread(thread_id)
            
            # Only add conversation history for NEW threads
            # Existing threads already maintain their own message history automatically
            # This prevents duplicate messages and improves performance
            if is_new_thread and conversation_history:
                logger.debug(f"   📖 Adding {len(conversation_history)} messages from history to NEW thread...")
                for hist_msg in conversation_history:
                    # Only add assistant and user messages (skip system)
                    if hist_msg.get("role") in ["user", "assistant"]:
                        await self.add_message_to_thread(
                            thread_id=thread_id,
                            role=hist_msg["role"],
                            content=hist_msg["content"]
                        )
            elif not is_new_thread:
                logger.debug(f"   ⏭️  Skipping history - existing thread already maintains message history (prevents duplicates)")
            
            # Always add the current user message
            logger.info(f"   💬 Adding user message to thread: {message[:100]}...")
            await self.add_message_to_thread(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # Verify the message was added by checking thread messages
            try:
                recent_messages = self._client.beta.threads.messages.list(
                    thread_id=thread_id,
                    order="desc",
                    limit=3
                )
                if recent_messages.data:
                    latest_user_msg = next((msg for msg in recent_messages.data if msg.role == "user"), None)
                    if latest_user_msg:
                        latest_content = latest_user_msg.content[0].text.value if latest_user_msg.content else "N/A"
                        logger.debug(f"   ✅ Verified latest user message in thread: {latest_content[:50]}...")
            except Exception as verify_err:
                logger.warning(f"   ⚠️  Could not verify message: {str(verify_err)}")
            
            # Run the assistant
            logger.info(f"   🚀 Running assistant (ID: {assistant_id}) for message: {message[:100]}...")
            run = self._client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id
            )
            logger.debug(f"   📋 Run created - ID: {run.id}, Status: {run.status}")
            
            # Wait for run to complete
            logger.info("   ⏳ Waiting for assistant response...")
            max_wait_time = 60  # Maximum 60 seconds
            wait_time = 0
            while run.status in ["queued", "in_progress"]:
                if wait_time >= max_wait_time:
                    raise Exception("Run timeout - assistant took too long to respond")
                
                time.sleep(1)
                wait_time += 1
                run = self._client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
            
            if run.status == "completed":
                # Get run steps to find the message created by this run
                # This is more reliable than getting all messages
                try:
                    run_steps = self._client.beta.threads.runs.steps.list(
                        thread_id=thread_id,
                        run_id=run.id
                    )
                    
                    # Find the message creation step
                    message_creation_step = None
                    for step in run_steps.data:
                        if hasattr(step, 'step_details') and hasattr(step.step_details, 'type'):
                            if step.step_details.type == "message_creation":
                                message_creation_step = step
                                break
                    
                    if message_creation_step and hasattr(message_creation_step.step_details, 'message_creation'):
                        message_id = message_creation_step.step_details.message_creation.message_id
                        logger.debug(f"   📋 Found message ID from run step: {message_id}")
                        
                        # Retrieve the specific message
                        message = self._client.beta.threads.messages.retrieve(
                            thread_id=thread_id,
                            message_id=message_id
                        )
                        
                        # Extract text content
                        if message.content and len(message.content) > 0:
                            content = message.content[0].text.value
                            logger.info(f"   ✅ Response generated successfully from run {run.id}")
                            logger.debug(f"   📝 Response preview: {content[:100]}...")
                            logger.debug(f"   📝 Full response length: {len(content)} characters")
                            return {
                                "content": content,
                                "source": MessageSource.internal,
                                "thread_id": thread_id
                            }
                        else:
                            raise Exception("Assistant message has no content")
                    else:
                        logger.warning(f"   ⚠️  Could not find message creation step, falling back to message list")
                        raise Exception("No message creation step found")
                        
                except Exception as step_err:
                    logger.warning(f"   ⚠️  Could not get message from run steps: {str(step_err)}")
                    logger.info(f"   🔄 Falling back to message list method...")
                    
                    # Fallback: Get messages from the thread (newest first)
                    messages = self._client.beta.threads.messages.list(
                        thread_id=thread_id,
                        order="desc",  # Newest first
                        limit=5  # Only get last 5 messages
                    )
                    
                    # Get the newest assistant message (should be from this run)
                    assistant_message = None
                    for msg in messages.data:
                        if msg.role == "assistant":
                            assistant_message = msg
                            logger.debug(f"   ✅ Using newest assistant message (fallback method)")
                            break
                    
                    if assistant_message:
                        # Extract text content from message
                        if assistant_message.content and len(assistant_message.content) > 0:
                            content = assistant_message.content[0].text.value
                            logger.info(f"   ✅ Response generated successfully (fallback)")
                            logger.debug(f"   📝 Response preview: {content[:100]}...")
                            logger.debug(f"   📝 Full response length: {len(content)} characters")
                            return {
                                "content": content,
                                "source": MessageSource.internal,
                                "thread_id": thread_id
                            }
                        else:
                            raise Exception("Assistant message has no content")
                    else:
                        raise Exception("No assistant response found")
            else:
                error_msg = f"Run failed with status: {run.status}"
                if hasattr(run, 'last_error') and run.last_error:
                    error_msg += f" - {run.last_error.message}"
                raise Exception(error_msg)
            
        except Exception as e:
            logger.error(f"❌ Assistants API error: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Assistants API error: {str(e)}")

