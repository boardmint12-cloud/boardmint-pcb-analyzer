/**
 * API client for PCB Analyzer backend
 * Full-featured client with auth, projects, files, comments, and analyses
 */
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests if available
// Supabase stores auth in localStorage with project-specific key
api.interceptors.request.use(async (config) => {
  // Try to get token from Supabase's localStorage
  // Supabase uses format: sb-<project-ref>-auth-token
  const keys = Object.keys(localStorage)
  const supabaseKey = keys.find(key => key.startsWith('sb-') && key.endsWith('-auth-token'))
  
  if (supabaseKey) {
    try {
      const stored = localStorage.getItem(supabaseKey)
      if (stored) {
        const parsed = JSON.parse(stored)
        const accessToken = parsed?.access_token
        if (accessToken) {
          config.headers.Authorization = `Bearer ${accessToken}`
        }
      }
    } catch (e) {
      console.error('Failed to parse auth token:', e)
    }
  }
  return config
})

// ============================================
// INTERFACES
// ============================================

export interface Project {
  id: string
  name: string
  eda_tool: string
  status: string
  created_at: string
  updated_at?: string
  description?: string
  user_comment?: string
  file_tree?: FileNode
  extraction_status?: string
  organization_id?: string
  created_by?: string
  created_by_name?: string
  analysis_count?: number
  storage_path?: string
  metadata?: Record<string, any>
}

export interface FileNode {
  name: string
  path: string
  is_directory: boolean
  file_type?: string
  purpose?: string
  size_bytes?: number
  children?: FileNode[]
}

export interface FileInfo {
  path: string
  name: string
  file_type: string
  purpose: string
  description: string
  size_bytes: number
  connections: string[]
}

export interface ProjectStructure {
  project_type: string
  main_pcb_file?: string
  main_schematic_file?: string
  layer_count?: number
  has_bom: boolean
  has_gerbers: boolean
  has_3d_models: boolean
  file_count: number
  total_size_bytes: number
  description: string
  key_components: string[]
}

export interface FileComment {
  id: string
  project_id: string
  file_path: string
  comment: string
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface IssueComment {
  id: string
  analysis_id: string
  issue_id: string
  comment: string
  status: string
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface AnalysisJob {
  id: string
  project_id: string
  status: string
  created_at: string
}

export interface Issue {
  id: string
  issue_code: string
  severity: 'critical' | 'warning' | 'info'
  category: string
  title: string
  description: string
  suggested_fix: string
  affected_nets: string[]
  affected_components: string[]
  location_x?: number
  location_y?: number
  layer?: string
}

export interface AnalysisResults {
  job_id: string
  project_id: string
  status: string
  progress: string
  risk_level: 'low' | 'moderate' | 'high'
  summary: {
    critical: number
    warning: number
    info: number
  }
  board_info: {
    size_x: number
    size_y: number
    layer_count: number
    min_track_width?: number
  }
  board_summary?: {
    purpose: string
    description: string
    key_features: string[]
    main_components: string[]
    design_notes?: string
  }
  issues_by_category: Record<string, Issue[]>
  created_at: string
  completed_at: string
}

/**
 * Upload a PCB project ZIP file
 */
export const uploadProject = async (
  file: File,
  projectName?: string,
  edaTool: string = 'kicad'
): Promise<Project> => {
  const formData = new FormData()
  formData.append('file', file)
  if (projectName) {
    formData.append('project_name', projectName)
  }
  formData.append('eda_tool', edaTool)

  const response = await api.post('/api/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data.project
}

/**
 * Start analysis for a project
 */
export const startAnalysis = async (
  projectId: string,
  fabProfile: string = 'cheap_cn_8mil'
): Promise<AnalysisJob> => {
  const response = await api.post(`/api/analyze/${projectId}`, null, {
    params: { fab_profile: fabProfile },
  })

  return response.data.job
}

/**
 * Get analysis results
 */
export const getAnalysisResults = async (jobId: string): Promise<AnalysisResults> => {
  const response = await api.get(`/api/results/${jobId}`)
  return response.data
}

/**
 * List all projects
 */
export const listProjects = async (skip: number = 0, limit: number = 20): Promise<Project[]> => {
  const response = await api.get('/api/projects', {
    params: { skip, limit },
  })

  return response.data.projects
}

/**
 * Download PDF report
 */
export const downloadPDFReport = (jobId: string): string => {
  return `${API_BASE_URL}/api/export/${jobId}/pdf`
}

/**
 * Batch analyze multiple projects
 */
export const batchAnalyze = async (
  projectIds: string[],
  fabProfile: string = 'cheap_cn_8mil'
): Promise<{ success: boolean, jobs: AnalysisJob[] }> => {
  const response = await api.post('/api/analyze/batch', {
    project_ids: projectIds,
    profile_id: fabProfile
  })

  return response.data
}

/**
 * Health check
 */
export const healthCheck = async (): Promise<{ status: string }> => {
  const response = await api.get('/api/health')
  return response.data
}

// ============================================
// V2 PROJECT ENDPOINTS (Multi-tenant)
// ============================================

/**
 * Create a new project with file upload (V2 - Supabase backed)
 */
export const createProjectV2 = async (
  file: File,
  name: string,
  description?: string,
  userComment?: string
): Promise<Project> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('name', name)
  if (description) formData.append('description', description)
  if (userComment) formData.append('user_comment', userComment)

  const response = await api.post('/api/projects', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Get project details (V2)
 */
export const getProjectV2 = async (projectId: string): Promise<Project> => {
  const response = await api.get(`/api/projects/${projectId}`)
  return response.data
}

/**
 * Update project (name, description, comment)
 */
export const updateProject = async (
  projectId: string,
  updates: { name?: string; description?: string; user_comment?: string }
): Promise<void> => {
  await api.patch(`/api/projects/${projectId}`, updates)
}

/**
 * Delete project
 */
export const deleteProject = async (projectId: string): Promise<void> => {
  await api.delete(`/api/projects/${projectId}`)
}

/**
 * List projects for current org (V2)
 */
export const listProjectsV2 = async (): Promise<Project[]> => {
  const response = await api.get('/api/projects')
  // Ensure we always return an array
  const data = response.data
  if (Array.isArray(data)) {
    return data
  }
  // Handle wrapped response like { projects: [...] }
  if (data && Array.isArray(data.projects)) {
    return data.projects
  }
  console.warn('listProjectsV2: unexpected response format:', data)
  return []
}

// ============================================
// FILE TREE & STRUCTURE
// ============================================

/**
 * Get project file tree
 */
export const getProjectFiles = async (projectId: string): Promise<{
  project_id: string
  file_tree: FileNode
  file_count: number
  total_size_bytes: number
}> => {
  const response = await api.get(`/api/projects/${projectId}/files`)
  return response.data
}

/**
 * Get info about a specific file
 */
export const getFileInfo = async (projectId: string, filePath: string): Promise<FileInfo> => {
  const response = await api.get(`/api/projects/${projectId}/files/${encodeURIComponent(filePath)}`)
  return response.data
}

/**
 * Get project structure overview
 */
export const getProjectStructure = async (projectId: string): Promise<ProjectStructure> => {
  const response = await api.get(`/api/projects/${projectId}/structure`)
  return response.data
}

// ============================================
// FILE COMMENTS
// ============================================

/**
 * Get all file comments for a project
 */
export const getProjectFileComments = async (projectId: string): Promise<{ comments: FileComment[] }> => {
  const response = await api.get(`/api/projects/${projectId}/comments`)
  return response.data
}

/**
 * Get comments for a specific file
 */
export const getFileComments = async (projectId: string, filePath: string): Promise<{ comments: FileComment[] }> => {
  const response = await api.get(`/api/projects/${projectId}/files/${encodeURIComponent(filePath)}/comments`)
  return response.data
}

/**
 * Add a comment to a file
 */
export const addFileComment = async (
  projectId: string,
  filePath: string,
  comment: string
): Promise<FileComment> => {
  const response = await api.post(`/api/projects/${projectId}/files/${encodeURIComponent(filePath)}/comments`, {
    comment
  })
  return response.data
}

/**
 * Delete a file comment
 */
export const deleteFileComment = async (projectId: string, commentId: string): Promise<void> => {
  await api.delete(`/api/projects/${projectId}/comments/${commentId}`)
}

// ============================================
// DOWNLOAD
// ============================================

/**
 * Get download URL for project
 */
export const getProjectDownloadUrl = async (projectId: string): Promise<{ download_url: string; filename: string }> => {
  const response = await api.get(`/api/projects/${projectId}/download`)
  return response.data
}

/**
 * Get download URL for a specific file
 */
export const getFileDownloadUrl = async (projectId: string, filename: string): Promise<{ download_url: string }> => {
  const response = await api.get(`/api/projects/${projectId}/download/${encodeURIComponent(filename)}`)
  return response.data
}

// ============================================
// ANALYSIS V2
// ============================================

/**
 * Start analysis for a project (V2)
 */
export const startAnalysisV2 = async (projectId: string): Promise<{
  id: string
  project_id: string
  status: string
}> => {
  const response = await api.post(`/api/projects/${projectId}/analyze`)
  return response.data
}

/**
 * Get analysis details (V2)
 */
export const getAnalysisV2 = async (analysisId: string): Promise<any> => {
  const response = await api.get(`/api/analyses/${analysisId}`)
  return response.data
}

/**
 * List analyses for current org
 */
export const listAnalyses = async (limit: number = 50, status?: string): Promise<any[]> => {
  const params: any = { limit }
  if (status) params.status = status
  const response = await api.get('/api/analyses', { params })
  return response.data
}

/**
 * Get file purposes from analysis
 */
export const getAnalysisFilePurposes = async (analysisId: string): Promise<{
  analysis_id: string
  file_purposes: Record<string, FileInfo>
  file_count: number
}> => {
  const response = await api.get(`/api/analyses/${analysisId}/file-purposes`)
  return response.data
}

// ============================================
// ISSUE COMMENTS
// ============================================

/**
 * Get all issues with comments
 */
export const getAnalysisIssues = async (analysisId: string): Promise<{
  analysis_id: string
  issues: any[]
  total_issues: number
  drc_summary: any
}> => {
  const response = await api.get(`/api/analyses/${analysisId}/issues`)
  return response.data
}

/**
 * Get comments for a specific issue
 */
export const getIssueComments = async (analysisId: string, issueId: string): Promise<{ comments: IssueComment[] }> => {
  const response = await api.get(`/api/analyses/${analysisId}/issues/${issueId}/comments`)
  return response.data
}

/**
 * Add a comment to an issue
 */
export const addIssueComment = async (
  analysisId: string,
  issueId: string,
  comment: string,
  status?: string
): Promise<IssueComment> => {
  const response = await api.post(`/api/analyses/${analysisId}/issues/${issueId}/comments`, {
    comment,
    status
  })
  return response.data
}

/**
 * Update issue status
 */
export const updateIssueStatus = async (
  analysisId: string,
  issueId: string,
  status: string,
  comment?: string
): Promise<void> => {
  await api.patch(`/api/analyses/${analysisId}/issues/${issueId}/status`, {
    status,
    comment
  })
}

/**
 * Delete an issue comment
 */
export const deleteIssueComment = async (analysisId: string, commentId: string): Promise<void> => {
  await api.delete(`/api/analyses/${analysisId}/comments/${commentId}`)
}

/**
 * Get PDF download URL for analysis
 */
export const getAnalysisPdfUrl = async (analysisId: string): Promise<{ download_url: string }> => {
  const response = await api.get(`/api/analyses/${analysisId}/pdf`)
  return response.data
}

// ============================================
// VERSION MANAGEMENT
// ============================================

export interface ProjectVersion {
  id: string
  version_number: number
  version_name?: string
  description?: string
  original_filename: string
  file_size_bytes?: number
  eda_tool?: string
  uploaded_by: string
  uploaded_by_name?: string
  uploaded_by_avatar?: string
  created_at: string
}

export interface Contributor {
  user_id: string
  full_name: string
  email: string
  avatar_url?: string
  role: string
  contribution_count: number
}

/**
 * List all versions of a project
 */
export const listProjectVersions = async (projectId: string): Promise<ProjectVersion[]> => {
  const response = await api.get(`/api/projects/${projectId}/versions`)
  return response.data
}

/**
 * Upload a new version of a project
 */
export const createProjectVersion = async (
  projectId: string,
  file: File,
  versionName?: string,
  description?: string
): Promise<ProjectVersion> => {
  const formData = new FormData()
  formData.append('file', file)
  if (versionName) formData.append('version_name', versionName)
  if (description) formData.append('description', description)

  const response = await api.post(`/api/projects/${projectId}/versions`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * List all contributors to a project
 */
export const listProjectContributors = async (projectId: string): Promise<Contributor[]> => {
  const response = await api.get(`/api/projects/${projectId}/contributors`)
  return response.data
}

export default api
