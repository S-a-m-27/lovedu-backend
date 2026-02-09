-- Migration: Add file_type to course_files table
-- Run this SQL in your Supabase SQL Editor

-- Add file_type column to distinguish behavior PDFs from course content PDFs
ALTER TABLE course_files 
ADD COLUMN IF NOT EXISTS file_type TEXT DEFAULT 'content' CHECK (file_type IN ('behavior', 'content'));

-- Update existing files to be 'content' type (default)
UPDATE course_files SET file_type = 'content' WHERE file_type IS NULL;

-- Add index for file_type lookups
CREATE INDEX IF NOT EXISTS idx_course_files_file_type ON course_files(course_id, file_type);

-- Note: 
-- 'behavior' = PDFs that define agent behavior/rules/guidelines
-- 'content' = PDFs that contain course materials (syllabi, lecture notes, etc.)

