-- Migration: Add project versions for version control
-- This enables GitHub-like version tracking for PCB projects

-- ============================================
-- PROJECT VERSIONS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS project_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    version_name VARCHAR(100),  -- Optional: "v1.0", "Rev A", etc.
    description TEXT,           -- What changed in this version
    
    -- File info
    storage_path TEXT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT,
    file_tree JSONB,
    eda_tool VARCHAR(50),
    
    -- Tracking
    uploaded_by UUID NOT NULL REFERENCES users(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure version numbers are unique per project
    UNIQUE(project_id, version_number)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_project_versions_project_id ON project_versions(project_id);
CREATE INDEX IF NOT EXISTS idx_project_versions_uploaded_by ON project_versions(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_project_versions_org ON project_versions(organization_id);

-- ============================================
-- ADD CONTRIBUTORS TRACKING
-- ============================================

-- Track all users who have contributed to a project (via versions or analyses)
CREATE TABLE IF NOT EXISTS project_contributors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'contributor',  -- 'owner', 'contributor', 'viewer'
    first_contribution_at TIMESTAMPTZ DEFAULT NOW(),
    last_contribution_at TIMESTAMPTZ DEFAULT NOW(),
    contribution_count INTEGER DEFAULT 1,
    
    UNIQUE(project_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_project_contributors_project ON project_contributors(project_id);
CREATE INDEX IF NOT EXISTS idx_project_contributors_user ON project_contributors(user_id);

-- ============================================
-- UPDATE PROJECTS TABLE
-- ============================================

-- Add current version tracking to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS current_version_id UUID REFERENCES project_versions(id);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS version_count INTEGER DEFAULT 1;

-- ============================================
-- UPDATE USERS TABLE
-- ============================================

-- Add profile picture URL to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- ============================================
-- RLS POLICIES
-- ============================================

-- Enable RLS on new tables
ALTER TABLE project_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_contributors ENABLE ROW LEVEL SECURITY;

-- Project versions policies
CREATE POLICY "Users can view versions in their org" ON project_versions
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Users can create versions in their org" ON project_versions
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- Contributors policies
CREATE POLICY "Users can view contributors in their org" ON project_contributors
    FOR SELECT USING (
        project_id IN (
            SELECT id FROM projects WHERE organization_id IN (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    );

CREATE POLICY "Users can add contributors to their org projects" ON project_contributors
    FOR INSERT WITH CHECK (
        project_id IN (
            SELECT id FROM projects WHERE organization_id IN (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    );

-- ============================================
-- FUNCTION: Auto-update contributors
-- ============================================

CREATE OR REPLACE FUNCTION update_project_contributors()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert or update contributor record
    INSERT INTO project_contributors (project_id, user_id, role, first_contribution_at, last_contribution_at, contribution_count)
    VALUES (NEW.project_id, NEW.uploaded_by, 'contributor', NOW(), NOW(), 1)
    ON CONFLICT (project_id, user_id) DO UPDATE SET
        last_contribution_at = NOW(),
        contribution_count = project_contributors.contribution_count + 1;
    
    -- Update version count on project
    UPDATE projects SET version_count = (
        SELECT COUNT(*) FROM project_versions WHERE project_id = NEW.project_id
    ) WHERE id = NEW.project_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update contributors when version is added
DROP TRIGGER IF EXISTS trigger_update_contributors ON project_versions;
CREATE TRIGGER trigger_update_contributors
    AFTER INSERT ON project_versions
    FOR EACH ROW
    EXECUTE FUNCTION update_project_contributors();

-- ============================================
-- INITIAL DATA MIGRATION
-- ============================================

-- Create version 1 for all existing projects
INSERT INTO project_versions (
    project_id, 
    version_number, 
    version_name, 
    storage_path, 
    original_filename, 
    file_size_bytes, 
    file_tree, 
    eda_tool,
    uploaded_by, 
    organization_id, 
    created_at
)
SELECT 
    p.id,
    1,
    'v1.0',
    p.storage_path,
    COALESCE((p.metadata->>'original_filename')::text, p.name || '.zip'),
    COALESCE((p.metadata->>'file_size')::bigint, 0),
    p.file_tree,
    p.eda_tool,
    p.created_by,
    p.organization_id,
    p.created_at
FROM projects p
WHERE NOT EXISTS (
    SELECT 1 FROM project_versions pv WHERE pv.project_id = p.id
);

-- Create initial contributor records for project creators
INSERT INTO project_contributors (project_id, user_id, role, first_contribution_at)
SELECT p.id, p.created_by, 'owner', p.created_at
FROM projects p
WHERE NOT EXISTS (
    SELECT 1 FROM project_contributors pc WHERE pc.project_id = p.id AND pc.user_id = p.created_by
);
