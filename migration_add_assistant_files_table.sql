-- Create assistant_files table to track PDFs for agents
CREATE TABLE IF NOT EXISTS assistant_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assistant_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    openai_file_id TEXT,
    file_size BIGINT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uploaded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    UNIQUE(assistant_id, file_name)
);

-- Drop constraint if it exists, then add it
ALTER TABLE assistant_files
DROP CONSTRAINT IF EXISTS assistant_files_assistant_id_check;

ALTER TABLE assistant_files
ADD CONSTRAINT assistant_files_assistant_id_check
CHECK (assistant_id IN ('typeX', 'references', 'academicReferences', 'therapyGPT', 'whatsTrendy'));

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_assistant_files_assistant_id ON assistant_files(assistant_id);
CREATE INDEX IF NOT EXISTS idx_assistant_files_openai_file_id ON assistant_files(openai_file_id);

