-- Migration: Add 'course' to chat_sessions assistant_id CHECK constraint
-- Run this SQL in your Supabase SQL Editor

-- Drop the existing constraint
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_assistant_id_check;

-- Add the new constraint with 'course' included
ALTER TABLE chat_sessions ADD CONSTRAINT chat_sessions_assistant_id_check 
    CHECK (assistant_id IN ('typeX', 'references', 'academicReferences', 'therapyGPT', 'whatsTrendy', 'course'));

