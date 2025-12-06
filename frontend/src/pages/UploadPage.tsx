import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import UploadZone from '@/components/UploadZone'
import { createProjectV2 } from '@/lib/api'
import { CheckCircle, ArrowRight, Upload, FileText } from 'lucide-react'

export default function UploadPage() {
  const navigate = useNavigate()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [projectName, setProjectName] = useState('')
  const [projectDescription, setProjectDescription] = useState('')
  const [projectComment, setProjectComment] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<string>('')

  const handleFileSelect = (file: File) => {
    setSelectedFile(file)
    if (!projectName) {
      // Clean up filename for project name
      let name = file.name
      for (const ext of ['.zip', '.kicad_pcb', '.brd', '.PcbDoc', '.pcbdoc']) {
        name = name.replace(ext, '')
      }
      setProjectName(name)
    }
    setError(null)
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file')
      return
    }

    if (!projectName.trim()) {
      setError('Please enter a project name')
      return
    }

    setIsUploading(true)
    setError(null)
    setUploadProgress('Uploading file...')

    try {
      // Create project (V2 - Supabase backed, includes file tree extraction)
      setUploadProgress('Processing and extracting files...')
      const project = await createProjectV2(
        selectedFile, 
        projectName.trim(),
        projectDescription.trim() || undefined,
        projectComment.trim() || undefined
      )
      
      setUploadProgress('✓ Project created successfully!')
      
      // Short delay to show success message, then navigate
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      // Navigate to project detail page (not directly to analysis)
      navigate(`/project/${project.id}`)
    } catch (err: any) {
      console.error('Upload failed:', err)
      const errorDetail = err.response?.data?.detail || 'Upload failed. Please try again.'
      // Provide helpful message for common errors
      if (errorDetail === 'Invalid ZIP file') {
        setError('Invalid ZIP file. Please ensure the file is a valid ZIP archive containing PCB files.')
      } else {
        setError(errorDetail)
      }
      setIsUploading(false)
      setUploadProgress('')
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-100 mb-2">
          Upload PCB Project
        </h1>
        <p className="text-gray-300">
          Upload ZIP archives or single files (.kicad_pcb, .brd, Gerber, etc.) - format auto-detected
        </p>
      </div>

      {/* Upload Zone */}
      <div className="mb-8">
        <UploadZone onFileSelect={handleFileSelect} isUploading={isUploading} />
      </div>

      {/* File Selected */}
      {selectedFile && !isUploading && (
        <div className="card mb-8">
          <div className="flex items-center space-x-3 mb-6">
            <CheckCircle className="h-6 w-6 text-green-600" />
            <div>
              <p className="font-medium text-gray-100">File selected</p>
              <p className="text-sm text-gray-300">{selectedFile.name} • {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          </div>

          {/* Project Settings */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Project Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg focus:ring-2 focus:ring-pcbGreen/50 focus:border-pcbGreen"
                placeholder="My PCB Project"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Description <span className="text-gray-500">(optional)</span>
              </label>
              <input
                type="text"
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg focus:ring-2 focus:ring-pcbGreen/50 focus:border-pcbGreen"
                placeholder="Brief description of this PCB project"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Notes <span className="text-gray-500">(optional)</span>
              </label>
              <textarea
                value={projectComment}
                onChange={(e) => setProjectComment(e.target.value)}
                rows={3}
                className="w-full px-4 py-2 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg focus:ring-2 focus:ring-pcbGreen/50 focus:border-pcbGreen resize-none"
                placeholder="Any notes or comments about this project (revision info, special requirements, etc.)"
              />
              <p className="text-xs text-gray-400 mt-1">
                You can add more detailed comments after viewing the file structure
              </p>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}

          {/* Upload Progress */}
          {uploadProgress && (
            <div className="mt-4 p-3 bg-blue-900/40 border border-blue-700 rounded-lg text-blue-300 text-sm flex items-center gap-2">
              <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
              {uploadProgress}
            </div>
          )}

          {/* Submit Button */}
          <div className="mt-6 flex justify-end gap-3">
            <button
              onClick={() => {
                setSelectedFile(null)
                setProjectName('')
                setProjectDescription('')
                setProjectComment('')
              }}
              className="btn-secondary"
            >
              Clear
            </button>
            <button
              onClick={handleUpload}
              disabled={isUploading || !projectName.trim()}
              className="btn-primary flex items-center space-x-2"
            >
              {isUploading ? (
                <>
                  <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <Upload className="h-5 w-5" />
                  <span>Upload Project</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
