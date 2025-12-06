import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listProjectsV2, batchAnalyze } from '@/lib/api'
import { Loader2, Upload, FolderOpen, Zap, GitBranch } from 'lucide-react'
import { formatDate } from '@/lib/utils'
import Avatar, { AvatarGroup } from '@/components/Avatar'

// Extended project type with version info
interface ProjectWithVersions {
  id: string
  name: string
  description?: string
  eda_tool?: string
  status: string
  created_at: string
  updated_at: string
  version_count: number
  contributors: Array<{
    user_id: string
    full_name: string
    email: string
    avatar_url?: string | null
    role: string
    contribution_count: number
  }>
  created_by_name?: string
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectWithVersions[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProjects, setSelectedProjects] = useState<Set<string>>(new Set())
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false)

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await listProjectsV2()
        setProjects(data as ProjectWithVersions[])
        setLoading(false)
      } catch (err) {
        console.error('Failed to load projects:', err)
        setError('Failed to load projects')
        setLoading(false)
      }
    }

    fetchProjects()
  }, [])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <Loader2 className="h-16 w-16 text-pcbGreen animate-spin mb-4" />
        <p className="text-lg font-medium text-gray-300">Loading projects...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card max-w-2xl mx-auto text-center py-16">
        <p className="text-lg font-medium text-red-500">{error}</p>
      </div>
    )
  }

  const toggleProjectSelection = (projectId: string) => {
    setSelectedProjects(prev => {
      const newSet = new Set(prev)
      if (newSet.has(projectId)) {
        newSet.delete(projectId)
      } else {
        newSet.add(projectId)
      }
      return newSet
    })
  }

  const handleBatchAnalyze = async () => {
    if (selectedProjects.size === 0) return

    setIsBatchAnalyzing(true)
    try {
      const projectIds = Array.from(selectedProjects)
      const result = await batchAnalyze(projectIds, 'cheap_cn_8mil')
      
      if (result.jobs && result.jobs.length > 0) {
        navigate(`/dashboard/${result.jobs[0].id}`)
      }
      
      setSelectedProjects(new Set())
    } catch (err) {
      console.error('Batch analysis failed:', err)
      setError('Failed to start batch analysis')
    } finally {
      setIsBatchAnalyzing(false)
    }
  }

  // Get status badge color
  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'text-green-400'
      case 'uploaded':
        return 'text-blue-400'
      case 'processing':
        return 'text-yellow-400'
      case 'error':
        return 'text-red-400'
      default:
        return 'text-gray-400'
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-pcbGreen">Projects</h1>
          <p className="text-gray-400 mt-1">View and manage your PCB analysis projects</p>
        </div>
        <div className="flex items-center space-x-3">
          {selectedProjects.size > 0 && (
            <button
              onClick={handleBatchAnalyze}
              disabled={isBatchAnalyzing}
              className="btn-primary flex items-center space-x-2"
            >
              <Zap className="h-5 w-5" />
              <span>{isBatchAnalyzing ? 'Analyzing...' : `Analyze ${selectedProjects.size}`}</span>
            </button>
          )}
          <Link to="/upload" className="btn-primary flex items-center space-x-2">
            <Upload className="h-5 w-5" />
            <span>New Project</span>
          </Link>
        </div>
      </div>

      {/* Empty State */}
      {!projects || projects.length === 0 ? (
        <div className="card text-center py-16">
          <FolderOpen className="h-16 w-16 text-gray-600 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-200 mb-2">No projects yet</p>
          <p className="text-gray-400 mb-6">Upload your first PCB project to get started</p>
          <Link to="/upload" className="btn-primary">
            <Upload className="inline-block h-5 w-5 mr-2" />
            Upload Project
          </Link>
        </div>
      ) : (
        /* Project List */
        <div className="space-y-3">
          {(projects || []).map((project) => (
            <div 
              key={project.id} 
              className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 hover:border-pcbGreen/50 transition-all"
            >
              <div className="flex items-center justify-between">
                {/* Left: Project Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-3">
                    {/* Checkbox */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleProjectSelection(project.id)
                      }}
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        selectedProjects.has(project.id)
                          ? 'bg-pcbGreen border-pcbGreen'
                          : 'border-gray-600 hover:border-gray-400'
                      }`}
                    >
                      {selectedProjects.has(project.id) && (
                        <svg className="w-3 h-3 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                    
                    {/* Project Name */}
                    <Link 
                      to={`/project/${project.id}`}
                      className="text-pcbGreen hover:text-pcbGreen-light font-semibold text-lg truncate"
                    >
                      {project.name}
                    </Link>
                  </div>
                  
                  {/* Meta info */}
                  <div className="flex items-center space-x-3 mt-2 text-sm text-gray-400 ml-8">
                    <span className="capitalize">{project.eda_tool || 'Unknown'}</span>
                    <span>•</span>
                    <span>{formatDate(project.created_at)}</span>
                    <span>•</span>
                    <span className={getStatusColor(project.status)}>
                      {project.status === 'completed' ? 'Completed' : 
                       project.status === 'uploaded' ? 'Uploaded' : 
                       project.status}
                    </span>
                  </div>
                </div>

                {/* Center: Version Count */}
                <div className="flex items-center space-x-2 mx-6 text-gray-400">
                  <GitBranch className="h-4 w-4" />
                  <span className="text-sm">
                    {project.version_count || 1} version{(project.version_count || 1) > 1 ? 's' : ''}
                  </span>
                </div>

                {/* Right: Contributors & Button */}
                <div className="flex items-center space-x-4">
                  {/* Contributors */}
                  {project.contributors && project.contributors.length > 0 ? (
                    <AvatarGroup 
                      contributors={project.contributors}
                      maxVisible={3}
                      size="sm"
                    />
                  ) : (
                    <Avatar 
                      name={project.created_by_name || 'Unknown'} 
                      size="sm"
                    />
                  )}

                  {/* View Details Button */}
                  <Link
                    to={`/project/${project.id}`}
                    className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm font-medium transition-colors"
                  >
                    View Details
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
