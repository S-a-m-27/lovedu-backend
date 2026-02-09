-- Migration: Add openai_file_id to course_files table
-- This stores the OpenAI file ID so we can reuse files instead of re-uploading them

ALTER TABLE course_files 
ADD COLUMN IF NOT EXISTS openai_file_id TEXT;

CREATE INDEX IF NOT EXISTS idx_course_files_openai_file_id ON course_files(openai_file_id);

-- Add comment
COMMENT ON COLUMN course_files.openai_file_id IS 'OpenAI file ID for this file, used to avoid re-uploading the same file';

