-- Migration: Add Service Role Policies for chat_sessions and messages
-- This allows the backend (using service role key) to bypass RLS when needed
-- Run this SQL in your Supabase SQL Editor

-- Service Role Policies for chat_sessions
-- Drop existing service role policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Service role can insert chat sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Service role can update chat sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Service role can delete chat sessions" ON chat_sessions;

-- Allow service role (backend) to insert chat sessions
CREATE POLICY "Service role can insert chat sessions"
    ON chat_sessions FOR INSERT
    WITH CHECK (true);

-- Allow service role to update chat sessions
CREATE POLICY "Service role can update chat sessions"
    ON chat_sessions FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- Allow service role to delete chat sessions
CREATE POLICY "Service role can delete chat sessions"
    ON chat_sessions FOR DELETE
    USING (true);

-- Service Role Policies for messages
-- Drop existing service role policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Service role can insert messages" ON messages;
DROP POLICY IF EXISTS "Service role can update messages" ON messages;
DROP POLICY IF EXISTS "Service role can delete messages" ON messages;

-- Allow service role to insert messages
CREATE POLICY "Service role can insert messages"
    ON messages FOR INSERT
    WITH CHECK (true);

-- Allow service role to update messages
CREATE POLICY "Service role can update messages"
    ON messages FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- Allow service role to delete messages
CREATE POLICY "Service role can delete messages"
    ON messages FOR DELETE
    USING (true);
