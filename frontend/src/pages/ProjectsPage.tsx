import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listProjects, Project, batchAnalyze } from '@/lib/api'
import { Loader2, Upload, FolderOpen, Zap, CheckSquare, Square } from 'lucide-react'
import { formatDate } from '@/lib/utils'

export default function ProjectsPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProjects, setSelectedProjects] = useState<Set<string>>(new Set())
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false)

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await listProjects()
        setProjects(data)
        setLoading(false)
      } catch (err) {
        setError('Failed to load projects')
        setLoading(false)
      }
    }

    fetchProjects()
  }, [])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <Loader2 className="h-16 w-16 text-primary-600 animate-spin mb-4" />
        <p className="text-lg font-medium text-gray-300">Loading projects...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card max-w-2xl mx-auto text-center py-16">
        <p className="text-lg font-medium text-red-600">{error}</p>
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
      
      // Navigate to first job's dashboard
      if (result.jobs && result.jobs.length > 0) {
        navigate(`/dashboard/${result.jobs[0].id}`)
      }
      
      // Clear selection
      setSelectedProjects(new Set())
    } catch (err) {
      console.error('Batch analysis failed:', err)
      setError('Failed to start batch analysis')
    } finally {
      setIsBatchAnalyzing(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-100">Projects</h1>
          <p className="text-gray-300 mt-1">View and manage your PCB analysis projects</p>
          {selectedProjects.size > 0 && (
            <p className="text-sm text-primary-400 mt-1">
              {selectedProjects.size} project{selectedProjects.size > 1 ? 's' : ''} selected
            </p>
          )}
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
          <Link to="/upload" className="btn-secondary flex items-center space-x-2">
            <Upload className="h-5 w-5" />
            <span>New Project</span>
          </Link>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="card text-center py-16">
          <FolderOpen className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-200 mb-2">No projects yet</p>
          <p className="text-gray-400 mb-6">Upload your first PCB project to get started</p>
          <Link to="/upload" className="btn-primary">
            <Upload className="inline-block h-5 w-5 mr-2" />
            Upload Project
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {projects.map((project) => (
            <div key={project.id} className="card hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4 flex-1">
                  {/* Checkbox for batch selection */}
                  <button
                    onClick={() => toggleProjectSelection(project.id)}
                    className="p-2 hover:bg-gray-800 rounded transition-colors"
                  >
                    {selectedProjects.has(project.id) ? (
                      <CheckSquare className="h-6 w-6 text-primary-500" />
                    ) : (
                      <Square className="h-6 w-6 text-gray-600" />
                    )}
                  </button>
                  
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-100 mb-1">{project.name}</h3>
                    <div className="flex items-center space-x-4 text-sm text-gray-400">
                      <span className="capitalize">{project.eda_tool}</span>
                      <span>•</span>
                      <span>{formatDate(project.created_at)}</span>
                      <span>•</span>
                      <span className="capitalize">{project.status}</span>
                    </div>
                  </div>
                </div>
                <Link
                  to={`/dashboard/${project.id}`}
                  className="btn-secondary"
                >
                  View Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
