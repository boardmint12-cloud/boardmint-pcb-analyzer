import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  Play, 
  Download, 
  Save, 
  Loader2, 
  FileText,
  CircuitBoard,
  Layers,
  Package,
  MessageSquare,
  Info,
  ChevronRight,
  ExternalLink,
  GitBranch,
  Upload,
  Clock,
  User
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import FileTree, { FileNode } from '@/components/FileTree'
import CommentBox, { Comment, CommentModal } from '@/components/CommentBox'
import Avatar from '@/components/Avatar'
import { formatDate } from '@/lib/utils'
import {
  getProjectV2,
  updateProject,
  getProjectFiles,
  getProjectStructure,
  getProjectFileComments,
  addFileComment,
  deleteFileComment,
  startAnalysisV2,
  getProjectDownloadUrl,
  listProjectVersions,
  createProjectVersion,
  Project,
  ProjectStructure,
  FileComment,
  ProjectVersion
} from '@/lib/api'

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  
  // State
  const [project, setProject] = useState<Project | null>(null)
  const [structure, setStructure] = useState<ProjectStructure | null>(null)
  const [fileTree, setFileTree] = useState<FileNode | null>(null)
  const [fileComments, setFileComments] = useState<FileComment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Edit state
  const [userComment, setUserComment] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  
  // File detail modal
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null)
  const [showFileCommentModal, setShowFileCommentModal] = useState(false)
  const [selectedFileForComment, setSelectedFileForComment] = useState<FileNode | null>(null)
  
  // Version state
  const [versions, setVersions] = useState<ProjectVersion[]>([])
  const [showVersionModal, setShowVersionModal] = useState(false)
  const [isUploadingVersion, setIsUploadingVersion] = useState(false)
  const [newVersionFile, setNewVersionFile] = useState<File | null>(null)
  const [newVersionName, setNewVersionName] = useState('')
  const [newVersionDescription, setNewVersionDescription] = useState('')
  const versionFileInputRef = useRef<HTMLInputElement>(null)
  
  // Load project data
  useEffect(() => {
    if (!projectId) return
    
    const loadProject = async () => {
      try {
        setLoading(true)
        
        // Load project, file tree, structure, comments, and versions in parallel
        const [projectData, filesData, structureData, commentsData, versionsData] = await Promise.all([
          getProjectV2(projectId),
          getProjectFiles(projectId).catch(() => null),
          getProjectStructure(projectId).catch(() => null),
          getProjectFileComments(projectId).catch(() => ({ comments: [] })),
          listProjectVersions(projectId).catch(() => [])
        ])
        
        setProject(projectData)
        setUserComment(projectData.user_comment || '')
        setVersions(versionsData)
        
        if (filesData) {
          setFileTree(filesData.file_tree)
        } else if (projectData.file_tree) {
          setFileTree(projectData.file_tree)
        }
        
        if (structureData) {
          setStructure(structureData)
        }
        
        setFileComments(commentsData.comments)
        
      } catch (err: any) {
        console.error('Failed to load project:', err)
        setError(err.response?.data?.detail || 'Failed to load project')
      } finally {
        setLoading(false)
      }
    }
    
    loadProject()
  }, [projectId])
  
  // Save project comment
  const handleSave = async () => {
    if (!projectId || isSaving) return
    
    setIsSaving(true)
    setSaveMessage(null)
    try {
      await updateProject(projectId, { user_comment: userComment })
      // Update local state
      if (project) {
        setProject({ ...project, user_comment: userComment })
      }
      setSaveMessage('✓ Project saved successfully!')
      // Clear message after 3 seconds
      setTimeout(() => setSaveMessage(null), 3000)
    } catch (err: any) {
      console.error('Failed to save:', err)
      setSaveMessage('✗ Failed to save: ' + (err.response?.data?.detail || err.message))
      setTimeout(() => setSaveMessage(null), 5000)
    } finally {
      setIsSaving(false)
    }
  }
  
  // Start analysis
  const handleStartAnalysis = async () => {
    if (!projectId || isAnalyzing) return
    
    setIsAnalyzing(true)
    try {
      const analysis = await startAnalysisV2(projectId)
      // Navigate to dashboard with analysis ID
      navigate(`/dashboard/${analysis.id}`)
    } catch (err: any) {
      console.error('Failed to start analysis:', err)
      setError(err.response?.data?.detail || 'Failed to start analysis')
      setIsAnalyzing(false)
    }
  }
  
  // Download project
  const handleDownload = async () => {
    if (!projectId) return
    
    try {
      const { download_url } = await getProjectDownloadUrl(projectId)
      window.open(download_url, '_blank')
    } catch (err) {
      console.error('Failed to get download URL:', err)
    }
  }
  
  // File selection
  const handleFileSelect = (file: FileNode) => {
    setSelectedFile(file)
  }
  
  // Add file comment
  const handleAddFileComment = (file: FileNode) => {
    setSelectedFileForComment(file)
    setShowFileCommentModal(true)
  }
  
  // Submit file comment
  const handleSubmitFileComment = async (comment: string) => {
    if (!projectId || !selectedFileForComment) return
    
    await addFileComment(projectId, selectedFileForComment.path, comment)
    
    // Refresh comments
    const { comments } = await getProjectFileComments(projectId)
    setFileComments(comments)
  }
  
  // Delete file comment
  const handleDeleteFileComment = async (commentId: string) => {
    if (!projectId) return
    
    await deleteFileComment(projectId, commentId)
    
    // Refresh comments
    const { comments } = await getProjectFileComments(projectId)
    setFileComments(comments)
  }
  
  // Group comments by file path
  const commentsByFile = fileComments.reduce((acc, comment) => {
    acc[comment.file_path] = (acc[comment.file_path] || 0) + 1
    return acc
  }, {} as Record<string, number>)
  
  // Get comments for selected file
  const selectedFileComments = selectedFileForComment
    ? fileComments.filter(c => c.file_path === selectedFileForComment.path)
    : []
  
  // Handle version upload
  const handleVersionFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setNewVersionFile(file)
      if (!newVersionName) {
        setNewVersionName(`v${(versions.length || 0) + 2}.0`)
      }
    }
  }
  
  const handleUploadVersion = async () => {
    if (!projectId || !newVersionFile || isUploadingVersion) return
    
    setIsUploadingVersion(true)
    try {
      const newVersion = await createProjectVersion(
        projectId,
        newVersionFile,
        newVersionName || undefined,
        newVersionDescription || undefined
      )
      
      // Add to versions list
      setVersions(prev => [newVersion, ...prev])
      
      // Reset form
      setNewVersionFile(null)
      setNewVersionName('')
      setNewVersionDescription('')
      setShowVersionModal(false)
      
      setSaveMessage('✓ New version uploaded successfully!')
      setTimeout(() => setSaveMessage(null), 3000)
    } catch (err: any) {
      console.error('Failed to upload version:', err)
      setSaveMessage('✗ Failed to upload version: ' + (err.response?.data?.detail || err.message))
      setTimeout(() => setSaveMessage(null), 5000)
    } finally {
      setIsUploadingVersion(false)
    }
  }
  
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <Loader2 className="h-16 w-16 text-pcbGreen animate-spin mb-4" />
        <p className="text-lg font-medium text-gray-300">Loading project...</p>
      </div>
    )
  }
  
  if (error || !project) {
    return (
      <div className="card max-w-2xl mx-auto text-center py-16">
        <p className="text-lg font-medium text-red-500 mb-4">{error || 'Project not found'}</p>
        <button onClick={() => navigate('/projects')} className="btn-primary">
          <ArrowLeft className="inline-block h-5 w-5 mr-2" />
          Back to Projects
        </button>
      </div>
    )
  }
  
  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/projects')}
          className="text-pcbGreen hover:text-pcbGreen-light font-medium mb-2 inline-flex items-center"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Projects
        </button>
        
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-100">{project.name}</h1>
            {project.description && (
              <p className="text-gray-400 mt-1">{project.description}</p>
            )}
            {saveMessage && (
              <p className={`text-sm mt-2 ${saveMessage.startsWith('✓') ? 'text-green-400' : 'text-red-400'}`}>
                {saveMessage}
              </p>
            )}
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={isSaving || userComment === (project.user_comment || '')}
              className="btn-secondary flex items-center gap-2"
            >
              {isSaving ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Save className="h-5 w-5" />
              )}
              <span>{isSaving ? 'Saving...' : 'Save'}</span>
            </button>
            
            <button
              onClick={handleDownload}
              className="btn-secondary flex items-center gap-2"
            >
              <Download className="h-5 w-5" />
              <span>Download</span>
            </button>
            
            <button
              onClick={handleStartAnalysis}
              disabled={isAnalyzing}
              className="btn-primary flex items-center gap-2"
            >
              {isAnalyzing ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Play className="h-5 w-5" />
              )}
              <span>{isAnalyzing ? 'Starting...' : 'Analyze PCB'}</span>
            </button>
          </div>
        </div>
      </div>
      
      {/* Project Info Cards */}
      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        {/* Project Structure Card */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <CircuitBoard className="h-5 w-5 text-pcbGreen" />
            <h3 className="font-semibold text-gray-200">Project Info</h3>
          </div>
          
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">EDA Tool</span>
              <span className="text-gray-200 capitalize">{project.eda_tool || 'Unknown'}</span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <span className="text-gray-200 capitalize">{project.extraction_status || 'Uploaded'}</span>
            </div>
            
            {structure && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-500">Files</span>
                  <span className="text-gray-200">{structure.file_count}</span>
                </div>
                
                {structure.layer_count && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Layers</span>
                    <span className="text-gray-200">{structure.layer_count}</span>
                  </div>
                )}
                
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-800">
                  {structure.has_gerbers && (
                    <span className="px-2 py-1 text-xs bg-purple-900/50 text-purple-300 rounded">Gerbers</span>
                  )}
                  {structure.has_bom && (
                    <span className="px-2 py-1 text-xs bg-yellow-900/50 text-yellow-300 rounded">BOM</span>
                  )}
                  {structure.has_3d_models && (
                    <span className="px-2 py-1 text-xs bg-cyan-900/50 text-cyan-300 rounded">3D</span>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
        
        {/* Key Components Card */}
        {structure && structure.key_components.length > 0 && (
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <Package className="h-5 w-5 text-blue-400" />
              <h3 className="font-semibold text-gray-200">Key Components</h3>
            </div>
            
            <div className="space-y-2">
              {structure.key_components.map((component, index) => (
                <div key={index} className="flex items-center gap-2 text-sm text-gray-300">
                  <ChevronRight className="h-4 w-4 text-gray-600" />
                  {component}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Main Files Card */}
        {structure && (
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="h-5 w-5 text-green-400" />
              <h3 className="font-semibold text-gray-200">Main Files</h3>
            </div>
            
            <div className="space-y-3 text-sm">
              {structure.main_pcb_file && (
                <div>
                  <span className="text-gray-500 block text-xs mb-1">PCB Layout</span>
                  <span className="text-gray-200 font-mono text-xs">{structure.main_pcb_file}</span>
                </div>
              )}
              
              {structure.main_schematic_file && (
                <div>
                  <span className="text-gray-500 block text-xs mb-1">Schematic</span>
                  <span className="text-gray-200 font-mono text-xs">{structure.main_schematic_file}</span>
                </div>
              )}
              
              {structure.description && (
                <p className="text-gray-400 text-xs mt-3 pt-3 border-t border-gray-800">
                  {structure.description}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
      
      {/* Main Content Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* File Tree */}
        <div>
          {fileTree ? (
            <FileTree
              tree={fileTree}
              onFileSelect={handleFileSelect}
              onAddComment={handleAddFileComment}
              selectedPath={selectedFile?.path}
              fileComments={commentsByFile}
            />
          ) : (
            <div className="card text-center py-12">
              <Layers className="h-12 w-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400">File tree not available</p>
            </div>
          )}
        </div>
        
        {/* Right Panel: File Details + Project Comment */}
        <div className="space-y-6">
          {/* Selected File Details */}
          {selectedFile && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Info className="h-5 w-5 text-blue-400" />
                  <h3 className="font-semibold text-gray-200">File Details</h3>
                </div>
                <button
                  onClick={() => handleAddFileComment(selectedFile)}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                >
                  <MessageSquare className="h-3 w-3" />
                  Add Comment
                </button>
              </div>
              
              <div className="space-y-3 text-sm">
                <div>
                  <span className="text-gray-500 block text-xs mb-1">Name</span>
                  <span className="text-gray-200 font-mono">{selectedFile.name}</span>
                </div>
                
                {selectedFile.purpose && (
                  <div>
                    <span className="text-gray-500 block text-xs mb-1">Purpose</span>
                    <span className="text-gray-200">{selectedFile.purpose}</span>
                  </div>
                )}
                
                {selectedFile.file_type && (
                  <div>
                    <span className="text-gray-500 block text-xs mb-1">Type</span>
                    <span className="text-gray-200 capitalize">{selectedFile.file_type.replace('_', ' ')}</span>
                  </div>
                )}
                
                {selectedFile.size_bytes !== undefined && (
                  <div>
                    <span className="text-gray-500 block text-xs mb-1">Size</span>
                    <span className="text-gray-200">
                      {selectedFile.size_bytes < 1024 
                        ? `${selectedFile.size_bytes} B`
                        : selectedFile.size_bytes < 1024 * 1024
                          ? `${(selectedFile.size_bytes / 1024).toFixed(1)} KB`
                          : `${(selectedFile.size_bytes / 1024 / 1024).toFixed(2)} MB`
                      }
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Project Comment */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-amber-400" />
                <h3 className="font-semibold text-gray-200">Project Notes</h3>
              </div>
            </div>
            
            <textarea
              value={userComment}
              onChange={(e) => setUserComment(e.target.value)}
              placeholder="Add notes about this project..."
              rows={4}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-pcbGreen/50 focus:border-pcbGreen"
            />
            
            <div className="flex justify-end mt-3">
              <button
                onClick={handleSave}
                disabled={isSaving || userComment === (project.user_comment || '')}
                className="btn-secondary flex items-center gap-2 text-sm"
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                <span>Save Notes</span>
              </button>
            </div>
          </div>
          
          {/* Version History */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-cyan-400" />
                <h3 className="font-semibold text-gray-200">
                  Version History
                  <span className="ml-2 text-sm text-gray-400 font-normal">
                    ({versions.length || 1} version{(versions.length || 1) > 1 ? 's' : ''})
                  </span>
                </h3>
              </div>
              <button
                onClick={() => setShowVersionModal(true)}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
              >
                <Upload className="h-3 w-3" />
                Upload New Version
              </button>
            </div>
            
            {/* Version list */}
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {versions.length > 0 ? (
                versions.map((version, index) => (
                  <div 
                    key={version.id}
                    className={`flex items-center justify-between p-3 rounded-lg ${
                      index === 0 ? 'bg-cyan-900/20 border border-cyan-800/50' : 'bg-gray-800/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Avatar 
                        name={version.uploaded_by_name || 'Unknown'} 
                        avatarUrl={version.uploaded_by_avatar}
                        size="sm" 
                      />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-gray-200 font-medium">
                            {version.version_name || `v${version.version_number}.0`}
                          </span>
                          {index === 0 && (
                            <span className="px-2 py-0.5 text-xs bg-cyan-900/50 text-cyan-300 rounded">Latest</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                          <span>{version.uploaded_by_name || 'Unknown'}</span>
                          <span>•</span>
                          <span>{formatDate(version.created_at)}</span>
                        </div>
                        {version.description && (
                          <p className="text-xs text-gray-500 mt-1">{version.description}</p>
                        )}
                      </div>
                    </div>
                    <div className="text-xs text-gray-500">
                      {version.original_filename}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-4 text-gray-500 text-sm">
                  <p>Original version uploaded with project</p>
                </div>
              )}
            </div>
          </div>
          
          {/* Analysis History */}
          {project.analysis_count !== undefined && project.analysis_count > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="h-5 w-5 text-purple-400" />
                <h3 className="font-semibold text-gray-200">Previous Analyses</h3>
              </div>
              
              <p className="text-sm text-gray-400">
                This project has {project.analysis_count} previous analysis{project.analysis_count > 1 ? 'es' : ''}.
              </p>
              
              <button
                onClick={() => navigate(`/projects/${projectId}/analyses`)}
                className="mt-3 text-sm text-purple-400 hover:text-purple-300 flex items-center gap-1"
              >
                View History
                <ExternalLink className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* File Comment Modal */}
      <CommentModal
        isOpen={showFileCommentModal}
        onClose={() => {
          setShowFileCommentModal(false)
          setSelectedFileForComment(null)
        }}
        title={`Comments: ${selectedFileForComment?.name || ''}`}
      >
        <CommentBox
          comments={selectedFileComments.map(c => ({
            id: c.id,
            comment: c.comment,
            created_by: c.created_by,
            created_by_name: c.created_by_name,
            created_at: c.created_at
          }))}
          onAddComment={handleSubmitFileComment}
          onDeleteComment={handleDeleteFileComment}
          currentUserId={user?.id}
          placeholder={`Add a comment about ${selectedFileForComment?.name}...`}
          title="File Comments"
        />
      </CommentModal>
      
      {/* Version Upload Modal */}
      {showVersionModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-md">
            <div className="p-6 border-b border-gray-700">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-gray-100">Upload New Version</h2>
                <button 
                  onClick={() => {
                    setShowVersionModal(false)
                    setNewVersionFile(null)
                    setNewVersionName('')
                    setNewVersionDescription('')
                  }}
                  className="text-gray-400 hover:text-gray-200"
                >
                  ✕
                </button>
              </div>
            </div>
            
            <div className="p-6 space-y-4">
              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Select File <span className="text-red-400">*</span>
                </label>
                <input
                  ref={versionFileInputRef}
                  type="file"
                  accept=".zip,.kicad_pcb,.brd,.PcbDoc"
                  onChange={handleVersionFileSelect}
                  className="hidden"
                />
                <button
                  onClick={() => versionFileInputRef.current?.click()}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-gray-300 hover:border-cyan-500 transition-colors flex items-center justify-center gap-2"
                >
                  <Upload className="h-5 w-5" />
                  {newVersionFile ? newVersionFile.name : 'Choose file...'}
                </button>
                {newVersionFile && (
                  <p className="text-xs text-gray-500 mt-1">
                    {(newVersionFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                )}
              </div>
              
              {/* Version Name */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Version Name
                </label>
                <input
                  type="text"
                  value={newVersionName}
                  onChange={(e) => setNewVersionName(e.target.value)}
                  placeholder={`v${(versions.length || 0) + 2}.0`}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500"
                />
              </div>
              
              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  What changed?
                </label>
                <textarea
                  value={newVersionDescription}
                  onChange={(e) => setNewVersionDescription(e.target.value)}
                  placeholder="Describe the changes in this version..."
                  rows={3}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500"
                />
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-700 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowVersionModal(false)
                  setNewVersionFile(null)
                  setNewVersionName('')
                  setNewVersionDescription('')
                }}
                className="px-4 py-2 text-gray-400 hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleUploadVersion}
                disabled={!newVersionFile || isUploadingVersion}
                className="btn-primary flex items-center gap-2"
              >
                {isUploadingVersion ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                {isUploadingVersion ? 'Uploading...' : 'Upload Version'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
