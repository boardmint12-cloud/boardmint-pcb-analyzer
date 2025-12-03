/**
 * API client for PCB Analyzer backend
 */
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface Project {
  id: string
  name: string
  eda_tool: string
  status: string
  created_at: string
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

export default api
