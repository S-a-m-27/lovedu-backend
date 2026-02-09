-- Migration: Add OpenAI Assistant API fields to chat_sessions
-- Run this SQL in your Supabase SQL Editor

-- Add OpenAI assistant_id and thread_id fields for course chats using Assistants API
ALTER TABLE chat_sessions 
ADD COLUMN IF NOT EXISTS openai_assistant_id TEXT,
ADD COLUMN IF NOT EXISTS openai_thread_id TEXT,
ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES courses(id) ON DELETE SET NULL;

-- Add index for course_id lookups
CREATE INDEX IF NOT EXISTS idx_chat_sessions_course_id ON chat_sessions(course_id);

-- Add index for OpenAI assistant_id lookups
CREATE INDEX IF NOT EXISTS idx_chat_sessions_openai_assistant_id ON chat_sessions(openai_assistant_id);

-- Note: These fields are optional and will be NULL for non-course chats
-- They are used to persist OpenAI Assistants API state for course-specific conversations

