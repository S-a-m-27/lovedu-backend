from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import os
import logging
import httpx
from app.models.chat import (
    ChatMessageRequest, ChatMessageResponse, ChatHistoryResponse,
    ChatSessionResponse, MessageResponse, MessageRole, MessageSource,
    AssistantType
)
from app.services.chat_service import ChatService
from app.services.openai_service import OpenAIService
from app.services.plan_service import PlanService
from app.api.auth.dependencies import get_current_user
from app.models.auth import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    current_user: UserResponse = Depends(get_current_user),
    chat_service: ChatService = Depends(lambda: ChatService()),
    openai_service: OpenAIService = Depends(lambda: OpenAIService()),
    plan_service: PlanService = Depends(lambda: PlanService())
):
    """
    Send a message and get AI response
    """
    logger.info(f"📥 Chat message request - User: {current_user.email}, Assistant: {request.assistant_id}, Mode: {request.mode}")
    logger.debug(f"   Message length: {len(request.message)} characters")
    logger.debug(f"   Chat session ID: {request.chat_session_id or 'None (will create new)'}")
    
    try:
        # Step 1: Get or create chat session
        session_id = request.chat_session_id
        course_id = request.course_id  # Get course_id from request first
        course_name = None
        
        if not session_id:
            logger.info(f"📝 Step 1: Creating new chat session for user: {current_user.id}")
            try:
                # If this is a course chat and course_id is provided, create course session
                if request.assistant_id == AssistantType.course and course_id:
                    from app.services.course_service import CourseService
                    course_service = CourseService()
                    course_session = course_service.create_course_chat_session(
                        user_id=current_user.id,
                        course_id=course_id
                    )
                    session_id = course_session["id"]
                    logger.info(f"   ✅ Course chat session created: {session_id} for course: {course_id}")
                else:
                    session_id = chat_service.create_chat_session(current_user.id, request.assistant_id)
                    logger.debug(f"   ✅ Session created: {session_id}")
            except Exception as e:
                logger.error(f"   ❌ Failed to create session: {str(e)}")
                raise
        else:
            logger.info(f"📖 Step 1: Using existing chat session: {session_id}")
            logger.debug(f"   Validating session belongs to user...")
            # Get session details including course_id
            try:
                sessions = chat_service.get_user_sessions(current_user.id)
                session = next((s for s in sessions if s.id == session_id), None)
                if session:
                    # Use course_id from session if not provided in request
                    if not course_id:
                        course_id = session.course_id
                    course_name = session.course_name
                    if course_id:
                        logger.info(f"   📚 Course chat detected - Course: {course_name} (ID: {course_id})")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not get session details: {str(e)}")
        
        # If we have course_id but no course_name, fetch it
        if course_id and not course_name:
            try:
                from app.services.course_service import CourseService
                course_service = CourseService()
                course = course_service.get_course_by_id(course_id)
                if course:
                    course_name = course.get("name")
                    logger.debug(f"   ✅ Fetched course name: {course_name}")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not fetch course name: {str(e)}")
        
        # If session exists but doesn't have course_id, and we have course_id from request, update the session
        if session_id and course_id:
            try:
                sessions = chat_service.get_user_sessions(current_user.id)
                session = next((s for s in sessions if s.id == session_id), None)
                if session and not session.course_id:
                    logger.info(f"   🔄 Updating session {session_id} with course_id: {course_id}")
                    # Update the session in the database
                    from app.services.supabase_service import SupabaseService
                    supabase = SupabaseService()
                    supabase.client.table("chat_sessions").update({
                        "course_id": course_id
                    }).eq("id", session_id).execute()
                    logger.info(f"   ✅ Session updated with course_id")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not update session course_id: {str(e)}")
        
        # Step 2: Save user message
        logger.info("💾 Step 2: Saving user message...")
        try:
            user_message = chat_service.save_message(
                session_id=session_id,
                content=request.message,
                role=MessageRole.user
            )
            logger.debug(f"   ✅ User message saved: {user_message.id}")
        except Exception as e:
            logger.error(f"   ❌ Failed to save user message: {str(e)}")
            raise
        
        # Step 3: Get conversation history
        logger.info("📖 Step 3: Fetching conversation history...")
        try:
            history = chat_service.get_chat_history(session_id, current_user.id)
            logger.debug(f"   ✅ Retrieved {len(history)} messages from history")
        except Exception as e:
            logger.error(f"   ❌ Failed to get chat history: {str(e)}")
            raise
        
        # Step 4: Convert history to OpenAI format
        logger.debug("🔄 Step 4: Converting history to OpenAI format...")
        conversation_history = []
        for msg in history[:-1]:  # Exclude the just-added user message
            conversation_history.append({
                "role": msg.role.value,
                "content": msg.content
            })
        logger.debug(f"   ✅ Converted {len(conversation_history)} messages for OpenAI")
        
        # Step 4.5: Track usage internally (no limits - free subscription for all)
        logger.info("📊 Step 4.5: Tracking usage (internal analytics only)...")
        try:
            # Estimate tokens for internal tracking (not blocking users)
            # OpenAI typically uses 1 token per ~4 characters, but we'll be conservative
            estimated_tokens = len(request.message) + len(conversation_history) * 100 + 500  # User msg + history + response estimate
            logger.debug(f"   📊 Estimated tokens for tracking: {estimated_tokens} (not blocking)")
            # Note: All users have free subscription - no usage limits enforced
            # Usage is tracked internally for analytics only
        except Exception as e:
            logger.error(f"   ⚠️  Usage tracking error (non-blocking): {str(e)}")
            # Don't block users if tracking fails
        
        # Step 5: Get files for course or agent
        course_files = []
        behavior_files = []
        assistant_files = []
        openai_file_ids = []
        use_assistants_api = False
        
        # Get assistant files if this is NOT a course chat
        # Note: Agents only have content PDFs (behavior is defined in system prompts)
        # Courses have both behavior PDFs (agent rules) and content PDFs (course materials)
        if not course_id and request.assistant_id != AssistantType.course:
            logger.info(f"📚 Step 5.1: Fetching content PDFs for agent: {request.assistant_id.value}")
            try:
                from app.services.admin_service import AdminService
                admin_service = AdminService()
                
                # Get content PDFs for this assistant (agents don't have behavior PDFs - behavior is in system prompts)
                assistant_files = admin_service.get_files_for_assistant(request.assistant_id.value)
                logger.info(f"   ✅ Found {len(assistant_files)} content PDFs for agent: {request.assistant_id.value}")
                
                if assistant_files:
                    logger.info(f"   📤 Checking/uploading {len(assistant_files)} files to OpenAI...")
                    for file_info in assistant_files:
                        try:
                            file_id = None
                            
                            # Check if file already has an OpenAI file ID stored
                            if file_info.openai_file_id:
                                try:
                                    openai_file = openai_service.client.files.retrieve(file_info.openai_file_id)
                                    if openai_file and hasattr(openai_file, 'id'):
                                        file_id = file_info.openai_file_id
                                        logger.debug(f"   ♻️  Reusing existing file {file_info.file_name} - ID: {file_id}")
                                except Exception as verify_err:
                                    logger.warning(f"   ⚠️  Stored file ID invalid for {file_info.file_name}, will re-upload: {str(verify_err)}")
                            
                            # Upload if we don't have a valid file ID
                            if not file_id:
                                # Download file from Supabase
                                file_content = admin_service.download_assistant_file(
                                    request.assistant_id.value,
                                    file_info.file_name
                                )
                                
                                # Upload to OpenAI
                                file_id = await openai_service.upload_file_to_openai(
                                    file_content=file_content,
                                    file_name=file_info.file_name
                                )
                                
                                # Store the OpenAI file ID in database
                                try:
                                    from app.services.supabase_service import SupabaseService
                                    supabase = SupabaseService()
                                    supabase.client.table("assistant_files").update({
                                        "openai_file_id": file_id
                                    }).eq("assistant_id", request.assistant_id.value).eq("file_name", file_info.file_name).execute()
                                    logger.debug(f"   💾 Stored OpenAI file ID for {file_info.file_name}")
                                except Exception as store_err:
                                    logger.warning(f"   ⚠️  Could not store OpenAI file ID: {str(store_err)}")
                                
                                logger.debug(f"   ✅ Uploaded file {file_info.file_name} - ID: {file_id}")
                            
                            openai_file_ids.append(file_id)
                        except Exception as file_err:
                            logger.warning(f"   ⚠️  Failed to process {file_info.file_name}: {str(file_err)}")
                            continue
                    
                    if openai_file_ids:
                        logger.info(f"   ✅ Uploaded {len(openai_file_ids)} files to OpenAI")
                        use_assistants_api = True
                    else:
                        logger.warning(f"   ⚠️  No files were successfully uploaded to OpenAI")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not fetch assistant files: {str(e)}")
                # Don't block the chat if file fetching fails
        
        # Get course files if this is a course chat
        if course_id:
            logger.info(f"📚 Step 5.1: Fetching files for course: {course_id}")
            try:
                from app.services.admin_service import AdminService
                admin_service = AdminService()
                
                # Get behavior PDFs (define agent behavior/rules)
                behavior_files = admin_service.get_course_files(course_id, file_type="behavior")
                logger.info(f"   ✅ Found {len(behavior_files)} behavior PDFs for course: {course_name}")
                
                # Get course content PDFs (course materials)
                course_files = admin_service.get_course_files(course_id, file_type="content")
                logger.info(f"   ✅ Found {len(course_files)} content PDFs for course: {course_name}")
                
                # Combine both types of files
                all_files = behavior_files + course_files
                
                # If we have any files, upload them to OpenAI and use Assistants API
                if all_files:
                    behavior_names = [f.file_name for f in behavior_files]
                    content_names = [f.file_name for f in course_files]
                    logger.debug(f"   📄 Behavior files ({len(behavior_files)}): {', '.join(behavior_names) if behavior_names else 'none'}")
                    logger.debug(f"   📄 Content files ({len(course_files)}): {', '.join(content_names) if content_names else 'none'}")
                    
                    logger.info(f"   📤 Checking/uploading {len(all_files)} files to OpenAI...")
                    for file_info in all_files:
                        try:
                            file_id = None
                            
                            # Check if file already has an OpenAI file ID stored
                            if file_info.openai_file_id:
                                # Verify the file still exists in OpenAI
                                try:
                                    openai_file = openai_service.client.files.retrieve(file_info.openai_file_id)
                                    if openai_file and hasattr(openai_file, 'id'):
                                        file_id = file_info.openai_file_id
                                        file_type_label = "behavior" if file_info.file_type == "behavior" else "content"
                                        logger.debug(f"   ♻️  Reusing existing {file_type_label} file {file_info.file_name} - ID: {file_id}")
                                except Exception as verify_err:
                                    logger.warning(f"   ⚠️  Stored file ID invalid for {file_info.file_name}, will re-upload: {str(verify_err)}")
                            
                            # Upload if we don't have a valid file ID
                            if not file_id:
                                # Download file from Supabase
                                file_content = admin_service.download_course_file(
                                    course_id, 
                                    file_info.file_name,
                                    file_type=file_info.file_type
                                )
                                
                                # Upload to OpenAI
                                file_id = await openai_service.upload_file_to_openai(
                                    file_content=file_content,
                                    file_name=file_info.file_name
                                )
                                
                                # Store the OpenAI file ID in database for future reuse
                                try:
                                    from app.services.supabase_service import SupabaseService
                                    supabase = SupabaseService()
                                    supabase.client.table("course_files").update({
                                        "openai_file_id": file_id
                                    }).eq("course_id", course_id).eq("file_name", file_info.file_name).execute()
                                    logger.debug(f"   💾 Stored OpenAI file ID for {file_info.file_name}")
                                except Exception as store_err:
                                    logger.warning(f"   ⚠️  Could not store OpenAI file ID: {str(store_err)}")
                                
                                file_type_label = "behavior" if file_info.file_type == "behavior" else "content"
                                logger.debug(f"   ✅ Uploaded {file_type_label} file {file_info.file_name} - ID: {file_id}")
                            
                            openai_file_ids.append(file_id)
                        except Exception as file_err:
                            logger.warning(f"   ⚠️  Failed to process {file_info.file_name}: {str(file_err)}")
                            continue
                    
                    if openai_file_ids:
                        logger.info(f"   ✅ Uploaded {len(openai_file_ids)} files to OpenAI ({len(behavior_files)} behavior, {len(course_files)} content)")
                        use_assistants_api = True
                    else:
                        logger.warning(f"   ⚠️  No files were successfully uploaded to OpenAI")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not fetch course files: {str(e)}")
                # Don't block the chat if file fetching fails
        
        # Step 6: Generate AI response
        logger.info("🤖 Step 6: Generating AI response...")
        try:
            if use_assistants_api and openai_file_ids:
                # Use Assistants API for chats with files (course or agent)
                if course_id:
                    logger.info("   📚 Using Assistants API for course chat with files...")
                else:
                    logger.info(f"   📚 Using Assistants API for agent chat with files...")
                
                # Get thread_id from session if available
                openai_ids = chat_service.get_session_openai_ids(session_id)
                thread_id = openai_ids.get("thread_id")
                stored_assistant_id = openai_ids.get("assistant_id")
                
                # Check if we can reuse the existing assistant (only for course chats)
                assistant_id = None
                if course_id and stored_assistant_id and openai_file_ids:
                    try:
                        # Retrieve the stored assistant to check its vector stores
                        existing_assistant = openai_service.client.beta.assistants.retrieve(stored_assistant_id)
                        
                        # Check if assistant has file_search tool with vector stores
                        has_file_search = False
                        existing_vector_store_ids = []
                        
                        if hasattr(existing_assistant, 'tool_resources') and existing_assistant.tool_resources:
                            if hasattr(existing_assistant.tool_resources, 'file_search'):
                                file_search = existing_assistant.tool_resources.file_search
                                if hasattr(file_search, 'vector_store_ids') and file_search.vector_store_ids:
                                    existing_vector_store_ids = file_search.vector_store_ids
                                    has_file_search = True
                        
                        # If assistant has vector stores, check if they contain the same files
                        if has_file_search and existing_vector_store_ids:
                            # Get files from the vector store(s)
                            api_key = os.getenv("OPENAI_API_KEY")
                            headers = {
                                "Authorization": f"Bearer {api_key}",
                                "OpenAI-Beta": "assistants=v2"
                            }
                            
                            # Get files from all vector stores
                            existing_file_ids = set()
                            for vs_id in existing_vector_store_ids:
                                try:
                                    async with httpx.AsyncClient() as http_client:
                                        # Get file IDs from vector store
                                        files_response = await http_client.get(
                                            f"https://api.openai.com/v1/vector_stores/{vs_id}/files",
                                            headers=headers,
                                            timeout=30.0
                                        )
                                        files_response.raise_for_status()
                                        files_data = files_response.json()
                                        if "data" in files_data:
                                            for file_item in files_data["data"]:
                                                if "id" in file_item:
                                                    existing_file_ids.add(file_item["id"])
                                except Exception as e:
                                    logger.warning(f"   ⚠️  Could not check vector store {vs_id}: {str(e)}")
                            
                            # Compare file sets (order doesn't matter)
                            current_file_ids = set(openai_file_ids)
                            
                            # Check if file sets match
                            if existing_file_ids and current_file_ids:
                                if existing_file_ids == current_file_ids:
                                    assistant_id = stored_assistant_id
                                    logger.info(f"   ✅ Reusing existing assistant (same {len(existing_file_ids)} files): {assistant_id}")
                                else:
                                    logger.info(f"   📝 Files changed - existing: {sorted(existing_file_ids)}, current: {sorted(current_file_ids)}")
                                    logger.info(f"   🔄 Creating new assistant with updated files...")
                            elif not existing_file_ids and current_file_ids:
                                # Assistant has no files but we have files - need new assistant
                                logger.info(f"   📝 Assistant has no files, but we have {len(current_file_ids)} files")
                                logger.info(f"   🔄 Creating new assistant with files...")
                            elif existing_file_ids and not current_file_ids:
                                # Assistant has files but we don't - reuse is OK
                                assistant_id = stored_assistant_id
                                logger.info(f"   ✅ Reusing existing assistant (no files needed): {assistant_id}")
                            else:
                                # Both empty - reuse is OK
                                assistant_id = stored_assistant_id
                                logger.info(f"   ✅ Reusing existing assistant (no files): {assistant_id}")
                        else:
                            # Assistant exists but has no vector stores, need to create new one
                            logger.info(f"   🔄 Existing assistant has no vector stores, creating new one...")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not verify existing assistant: {str(e)}")
                        logger.info(f"   🔄 Creating new assistant...")
                
                # Create new assistant if we don't have one to reuse
                if not assistant_id:
                    if course_id:
                        # Course assistant
                        assistant_id = await openai_service.get_or_create_course_assistant(
                            course_id=course_id,
                            course_name=course_name,
                            file_ids=openai_file_ids
                        )
                    else:
                        # Agent assistant
                        assistant_id = await openai_service.get_or_create_agent_assistant(
                            assistant_id=request.assistant_id,
                            file_ids=openai_file_ids
                        )
                    logger.info(f"   ✅ Created/using assistant: {assistant_id}")
                elif not openai_file_ids:
                    # No files, safe to reuse stored assistant
                    assistant_id = stored_assistant_id
                    logger.info(f"   ✅ Reusing stored assistant (no files): {assistant_id}")
                
                # Get or create thread
                thread_id, is_new_thread = await openai_service.get_or_create_thread(
                    thread_id=thread_id
                )
                
                # Generate response using Assistants API
                ai_response = await openai_service.generate_chat_response_with_assistants_api(
                    message=request.message,
                    assistant_id=assistant_id,
                    thread_id=thread_id,
                    conversation_history=conversation_history if is_new_thread else None
                )
                
                # Store assistant_id and thread_id in database for future use
                if "thread_id" in ai_response:
                    chat_service.update_session_openai_ids(
                        session_id=session_id,
                        openai_assistant_id=assistant_id,
                        openai_thread_id=ai_response["thread_id"]
                    )
                    logger.debug(f"   📝 Stored OpenAI IDs - Assistant: {assistant_id}, Thread: {ai_response['thread_id']}")
                
                logger.debug(f"   ✅ AI response generated - Length: {len(ai_response['content'])} characters")
            else:
                # Use regular chat completions for non-course chats or when files fail
                logger.info("   💬 Using regular chat completions...")
                ai_response = await openai_service.generate_chat_response(
                    message=request.message,
                    assistant_id=request.assistant_id,
                    mode=request.mode,
                    conversation_history=conversation_history if conversation_history else None,
                    course_id=course_id,
                    course_name=course_name,
                    course_files=course_files
                )
                logger.debug(f"   ✅ AI response generated - Length: {len(ai_response['content'])} characters")
                logger.debug(f"   ✅ Response source: {ai_response['source']}")
        except Exception as e:
            logger.error(f"   ❌ OpenAI API error: {str(e)}")
            logger.exception("   OpenAI error traceback:")
            raise
        
        # Step 7: Save assistant message
        logger.info("💾 Step 7: Saving assistant message...")
        try:
            # Handle source - OpenAI service returns MessageSource enum
            source = ai_response.get("source")
            if isinstance(source, str):
                # Convert string to MessageSource enum if needed
                source = MessageSource(source)
            
            assistant_message = chat_service.save_message(
                session_id=session_id,
                content=ai_response["content"],
                role=MessageRole.assistant,
                source=source
            )
            logger.debug(f"   ✅ Assistant message saved: {assistant_message.id}")
        except Exception as e:
            logger.error(f"   ❌ Failed to save assistant message: {str(e)}")
            raise
        
        # Step 7: Track usage internally for analytics (non-blocking - free subscription for all)
        logger.info("📈 Step 7: Tracking usage statistics (internal analytics only)...")
        try:
            # Calculate actual tokens used (rough estimate) for internal tracking
            actual_tokens = len(request.message) + len(ai_response["content"]) + len(conversation_history) * 100
            plan_service.increment_usage(current_user.id, tokens=actual_tokens)
            logger.debug(f"   ✅ Usage tracked internally - Tokens: {actual_tokens} (non-blocking)")
        except Exception as e:
            logger.error(f"   ⚠️  Failed to track usage (non-blocking): {str(e)}")
            # Don't fail the request if usage tracking fails - this is for analytics only
            logger.debug("   Continuing despite usage tracking error")
        
        logger.info(f"✅ Chat message processed successfully - Session: {session_id}")
        logger.debug(f"   Returning response with message ID: {assistant_message.id}")
        
        return ChatMessageResponse(
            message=assistant_message,
            chat_session_id=session_id,
            assistant_id=request.assistant_id,
            mode=request.mode
        )
        
    except HTTPException as http_ex:
        logger.error(f"❌ HTTP Exception in send_message - Status: {http_ex.status_code}, Detail: {http_ex.detail}")
        raise
    except ValueError as ve:
        error_msg = f"ValueError in send_message: {str(ve)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"   User: {current_user.email}, Assistant: {request.assistant_id}")
        logger.exception("Full ValueError traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process chat message: {str(ve)}"
        )
    except Exception as e:
        error_msg = f"Failed to process chat message: {str(e)}"
        error_type = type(e).__name__
        logger.error(f"❌ {error_msg}")
        logger.error(f"   Exception Type: {error_type}")
        logger.error(f"   User: {current_user.email}")
        logger.error(f"   Assistant: {request.assistant_id}, Mode: {request.mode}")
        logger.error(f"   Session ID: {request.chat_session_id or 'None'}")
        logger.error(f"   Exception Args: {e.args if hasattr(e, 'args') else 'N/A'}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    current_user: UserResponse = Depends(get_current_user),
    chat_service: ChatService = Depends(lambda: ChatService())
):
    """
    Get all chat sessions for current user
    """
    logger.info(f"📥 Get chat sessions request - User: {current_user.email}")
    
    try:
        sessions = chat_service.get_user_sessions(current_user.id)
        logger.info(f"✅ Retrieved {len(sessions)} sessions for user: {current_user.email}")
        return sessions
        
    except Exception as e:
        error_msg = f"Failed to get chat sessions: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
    chat_service: ChatService = Depends(lambda: ChatService())
):
    """
    Get specific chat session with all messages
    """
    logger.info(f"📥 Get chat session request - Session: {session_id}, User: {current_user.email}")
    
    try:
        # Get session info with course details
        sessions = chat_service.get_user_sessions(current_user.id)
        session = next((s for s in sessions if s.id == session_id), None)
        
        if not session:
            logger.warning(f"⚠️  Chat session not found: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        # Get messages
        messages = chat_service.get_chat_history(session_id, current_user.id)
        
        logger.info(f"✅ Retrieved session {session_id} with {len(messages)} messages")
        if session.course_id:
            logger.info(f"   Course: {session.course_name} (ID: {session.course_id})")
        
        return ChatHistoryResponse(
            session=session,
            messages=messages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to get chat session: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    assistant_id: str,
    current_user: UserResponse = Depends(get_current_user),
    chat_service: ChatService = Depends(lambda: ChatService())
):
    """
    Create a new chat session
    """
    logger.info(f"📥 Create chat session request - User: {current_user.email}, Assistant: {assistant_id}")
    
    try:
        assistant = AssistantType(assistant_id)
        
        session_id = chat_service.create_chat_session(current_user.id, assistant)
        
        # Get the created session
        sessions = chat_service.get_user_sessions(current_user.id)
        session = next((s for s in sessions if s.id == session_id), None)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created session"
            )
        
        logger.info(f"✅ Chat session created: {session_id}")
        return session
        
    except ValueError as e:
        logger.warning(f"⚠️  Invalid assistant_id: {assistant_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assistant_id: {assistant_id}"
        )
    except Exception as e:
        error_msg = f"Failed to create chat session: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
    chat_service: ChatService = Depends(lambda: ChatService())
):
    """
    Delete a chat session and all its messages
    """
    logger.info(f"📥 Delete chat session request - Session: {session_id}, User: {current_user.email}")
    
    try:
        success = chat_service.delete_chat_session(session_id, current_user.id)
        
        if success:
            logger.info(f"✅ Chat session deleted: {session_id}")
            return {"message": "Chat session deleted successfully", "session_id": session_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete chat session"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to delete chat session: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

