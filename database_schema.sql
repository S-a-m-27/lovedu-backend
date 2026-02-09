-- Database Schema for Multi-Agent Chat Application
-- Run this SQL in your Supabase SQL Editor

-- Chat Sessions Table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    assistant_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_count INTEGER NOT NULL DEFAULT 0
);

-- Add CHECK constraint for assistant_id (drop if exists for idempotency)
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_assistant_id_check;
ALTER TABLE chat_sessions ADD CONSTRAINT chat_sessions_assistant_id_check 
    CHECK (assistant_id IN ('typeX', 'references', 'academicReferences', 'therapyGPT', 'whatsTrendy', 'course'));

-- Messages Table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT CHECK (source IN ('internal', 'web'))
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(chat_session_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

-- Enable Row Level Security (RLS)
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies for chat_sessions
-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view their own chat sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Users can create their own chat sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Users can update their own chat sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Users can delete their own chat sessions" ON chat_sessions;

-- Users can only see their own chat sessions
CREATE POLICY "Users can view their own chat sessions"
    ON chat_sessions FOR SELECT
    USING (auth.uid() = user_id);

-- Users can create their own chat sessions
CREATE POLICY "Users can create their own chat sessions"
    ON chat_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own chat sessions
CREATE POLICY "Users can update their own chat sessions"
    ON chat_sessions FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can delete their own chat sessions
CREATE POLICY "Users can delete their own chat sessions"
    ON chat_sessions FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for messages
-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view messages from their sessions" ON messages;
DROP POLICY IF EXISTS "Users can insert messages into their sessions" ON messages;
DROP POLICY IF EXISTS "Users can update messages from their sessions" ON messages;
DROP POLICY IF EXISTS "Users can delete messages from their sessions" ON messages;

-- Users can view messages from their own chat sessions
CREATE POLICY "Users can view messages from their sessions"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions
            WHERE chat_sessions.id = messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- Users can insert messages into their own chat sessions
CREATE POLICY "Users can insert messages into their sessions"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM chat_sessions
            WHERE chat_sessions.id = messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- Users can update messages from their own chat sessions
CREATE POLICY "Users can update messages from their sessions"
    ON messages FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions
            WHERE chat_sessions.id = messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- Users can delete messages from their own chat sessions
CREATE POLICY "Users can delete messages from their sessions"
    ON messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions
            WHERE chat_sessions.id = messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
-- Drop trigger if it exists (for idempotency)
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;

CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- User Usage Table for tracking daily usage
-- NOTE: This is for INTERNAL tracking/analytics only - NOT exposed to users
-- All users have free subscription, but we track usage for analytics
CREATE TABLE IF NOT EXISTS user_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    pdf_uploads INTEGER NOT NULL DEFAULT 0,
    images_uploaded INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, usage_date)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_user_usage_user_id ON user_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_date ON user_usage(usage_date);

-- Enable RLS
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_usage
-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view their own usage" ON user_usage;
DROP POLICY IF EXISTS "Users can insert their own usage" ON user_usage;
DROP POLICY IF EXISTS "Users can update their own usage" ON user_usage;

CREATE POLICY "Users can view their own usage"
    ON user_usage FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own usage"
    ON user_usage FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own usage"
    ON user_usage FOR UPDATE
    USING (auth.uid() = user_id);

-- User Subscriptions Table for tracking subscriptions
-- NOTE: This is for INTERNAL tracking only - NOT exposed to users
-- All users are on 'free' plan by default (set in signup)
-- This table exists for future use or internal analytics
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL CHECK (plan IN ('free', 'basic', 'pro')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
    stripe_subscription_id TEXT, -- For future Stripe integration
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);

ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if it exists (for idempotency)
DROP POLICY IF EXISTS "Users can view their own subscriptions" ON user_subscriptions;

CREATE POLICY "Users can view their own subscriptions"
    ON user_subscriptions FOR SELECT
    USING (auth.uid() = user_id);

-- Note: Service role will be used for INSERT/UPDATE operations via backend

-- Courses Table for admin-created courses
CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code);
CREATE INDEX IF NOT EXISTS idx_courses_created_by ON courses(created_by);
CREATE INDEX IF NOT EXISTS idx_courses_is_active ON courses(is_active);

ALTER TABLE courses ENABLE ROW LEVEL SECURITY;

-- RLS Policies for courses
-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Anyone can view active courses" ON courses;
DROP POLICY IF EXISTS "Service role can insert courses" ON courses;
DROP POLICY IF EXISTS "Service role can update courses" ON courses;
DROP POLICY IF EXISTS "Service role can delete courses" ON courses;

-- Anyone can view active courses
CREATE POLICY "Anyone can view active courses"
    ON courses FOR SELECT
    USING (is_active = true);

-- Service role (backend) can insert courses
-- Note: Backend uses service role key which bypasses RLS, but we add policy for safety
CREATE POLICY "Service role can insert courses"
    ON courses FOR INSERT
    WITH CHECK (true);

-- Service role (backend) can update courses
CREATE POLICY "Service role can update courses"
    ON courses FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- Service role (backend) can delete courses (soft delete via is_active)
CREATE POLICY "Service role can delete courses"
    ON courses FOR DELETE
    USING (true);

-- Student Courses Table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS student_courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_student_courses_user_id ON student_courses(user_id);
CREATE INDEX IF NOT EXISTS idx_student_courses_course_id ON student_courses(course_id);

ALTER TABLE student_courses ENABLE ROW LEVEL SECURITY;

-- RLS Policies for student_courses
-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view their own enrolled courses" ON student_courses;
DROP POLICY IF EXISTS "Users can enroll in courses" ON student_courses;

CREATE POLICY "Users can view their own enrolled courses"
    ON student_courses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can enroll in courses"
    ON student_courses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Update chat_sessions to support course_id
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES courses(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_course_id ON chat_sessions(course_id);

-- Course Files Table (for admin-uploaded PDFs per course)
CREATE TABLE IF NOT EXISTS course_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size BIGINT,
    uploaded_by UUID NOT NULL REFERENCES auth.users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_course_files_course_id ON course_files(course_id);
CREATE INDEX IF NOT EXISTS idx_course_files_uploaded_by ON course_files(uploaded_by);

ALTER TABLE course_files ENABLE ROW LEVEL SECURITY;

-- RLS Policies for course_files
-- Drop existing policy if it exists (for idempotency)
DROP POLICY IF EXISTS "Anyone can view course files" ON course_files;

CREATE POLICY "Anyone can view course files"
    ON course_files FOR SELECT
    USING (true);

