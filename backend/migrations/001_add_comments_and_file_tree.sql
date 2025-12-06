-- ============================================================
-- BoardMint Supabase Migration: Comments & File Management
-- Version: 001
-- Description: Add file tree, comments, and cloud storage support
-- ============================================================

-- ============================================================
-- 1. EXTEND PROJECTS TABLE
-- ============================================================

-- Add user comment field for project-level notes
ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_comment TEXT;

-- Add file tree JSON structure
ALTER TABLE projects ADD COLUMN IF NOT EXISTS file_tree JSONB;

-- Add original filename tracking
ALTER TABLE projects ADD COLUMN IF NOT EXISTS original_filename TEXT;

-- Add file size tracking
ALTER TABLE projects ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

-- Add extraction status
ALTER TABLE projects ADD COLUMN IF NOT EXISTS extraction_status TEXT DEFAULT 'pending';

-- Add EDA tool detection result
ALTER TABLE projects ADD COLUMN IF NOT EXISTS eda_tool TEXT;

-- Add board metadata from parsing
ALTER TABLE projects ADD COLUMN IF NOT EXISTS board_metadata JSONB;

-- ============================================================
-- 2. FILE COMMENTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS file_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    comment TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure unique comment per user per file (can have multiple comments from different users)
    CONSTRAINT unique_user_file_comment UNIQUE (project_id, file_path, created_by, created_at)
);

-- Index for fast lookup by project
CREATE INDEX IF NOT EXISTS idx_file_comments_project ON file_comments(project_id);

-- Index for fast lookup by file path
CREATE INDEX IF NOT EXISTS idx_file_comments_file_path ON file_comments(project_id, file_path);

-- ============================================================
-- 3. ISSUE COMMENTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS issue_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    issue_id TEXT NOT NULL,  -- Issue ID from the analysis engine
    comment TEXT NOT NULL,
    status TEXT DEFAULT 'open',  -- open, acknowledged, resolved, wont_fix
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup by analysis
CREATE INDEX IF NOT EXISTS idx_issue_comments_analysis ON issue_comments(analysis_id);

-- Index for fast lookup by issue
CREATE INDEX IF NOT EXISTS idx_issue_comments_issue ON issue_comments(analysis_id, issue_id);

-- ============================================================
-- 4. EXTEND ANALYSES TABLE
-- ============================================================

-- Add file purposes (AI-detected purpose of each file)
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS file_purposes JSONB;

-- Add project structure (how files connect together)
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS project_structure JSONB;

-- Add storage path for PDF report in Supabase
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS pdf_storage_path TEXT;

-- Add raw issues JSON for detailed storage
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS issues_json JSONB;

-- ============================================================
-- 5. PROJECT FILES TABLE (for individual file tracking)
-- ============================================================

CREATE TABLE IF NOT EXISTS project_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,  -- Relative path within project
    file_name TEXT NOT NULL,
    file_extension TEXT,
    file_size_bytes BIGINT,
    file_type TEXT,  -- 'pcb', 'schematic', 'gerber', 'bom', 'documentation', 'other'
    purpose TEXT,  -- AI-detected purpose
    description TEXT,  -- AI-generated description
    connections JSONB,  -- Related files/components
    storage_path TEXT,  -- Path in Supabase Storage
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_project_file UNIQUE (project_id, file_path)
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_type ON project_files(project_id, file_type);

-- ============================================================
-- 6. ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on new tables
ALTER TABLE file_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE issue_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_files ENABLE ROW LEVEL SECURITY;

-- File comments: Users can only access comments in their organization's projects
CREATE POLICY file_comments_org_access ON file_comments
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE organization_id = (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    );

-- Issue comments: Users can only access comments in their organization's analyses
CREATE POLICY issue_comments_org_access ON issue_comments
    FOR ALL
    USING (
        analysis_id IN (
            SELECT id FROM analyses 
            WHERE organization_id = (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    );

-- Project files: Users can only access files in their organization's projects
CREATE POLICY project_files_org_access ON project_files
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE organization_id = (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    );

-- ============================================================
-- 7. STORAGE BUCKET SETUP
-- ============================================================

-- Note: Run these in Supabase Dashboard > Storage
-- 
-- 1. Create bucket: pcb-files (if not exists)
-- 2. Create bucket: analysis-reports (for PDF reports)
-- 
-- Bucket policies (set in dashboard):
-- pcb-files: Authenticated users can read/write to their org folder
-- analysis-reports: Authenticated users can read their org's reports

-- ============================================================
-- 8. HELPER FUNCTIONS
-- ============================================================

-- Function to get user's organization ID
CREATE OR REPLACE FUNCTION get_user_org_id(user_id UUID)
RETURNS UUID AS $$
    SELECT organization_id FROM users WHERE id = user_id;
$$ LANGUAGE SQL SECURITY DEFINER;

-- Function to check if user has access to project
CREATE OR REPLACE FUNCTION user_has_project_access(user_id UUID, p_project_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM projects p
        JOIN users u ON u.organization_id = p.organization_id
        WHERE p.id = p_project_id AND u.id = user_id
    );
$$ LANGUAGE SQL SECURITY DEFINER;

-- ============================================================
-- 9. UPDATED_AT TRIGGERS
-- ============================================================

-- Generic updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to file_comments
DROP TRIGGER IF EXISTS update_file_comments_updated_at ON file_comments;
CREATE TRIGGER update_file_comments_updated_at
    BEFORE UPDATE ON file_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply to issue_comments
DROP TRIGGER IF EXISTS update_issue_comments_updated_at ON issue_comments;
CREATE TRIGGER update_issue_comments_updated_at
    BEFORE UPDATE ON issue_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================
