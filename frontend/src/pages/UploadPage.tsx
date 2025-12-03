import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import UploadZone from '@/components/UploadZone'
import { uploadProject, startAnalysis } from '@/lib/api'
import { CheckCircle, ArrowRight } from 'lucide-react'

export default function UploadPage() {
  const navigate = useNavigate()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [projectName, setProjectName] = useState('')
  const [edaTool, setEdaTool] = useState('kicad')
  const [fabProfile, setFabProfile] = useState('cheap_cn_8mil')
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFileSelect = (file: File) => {
    setSelectedFile(file)
    if (!projectName) {
      setProjectName(file.name.replace('.zip', ''))
    }
    setError(null)
  }

  const handleStartAnalysis = async () => {
    if (!selectedFile) {
      setError('Please select a file')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      // Upload project
      const project = await uploadProject(selectedFile, projectName, edaTool)
      
      // Start analysis
      const job = await startAnalysis(project.id, fabProfile)
      
      // Navigate to dashboard
      navigate(`/dashboard/${job.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.')
      setIsUploading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-100 mb-2">
          Upload PCB Project
        </h1>
        <p className="text-gray-300">
          Upload your PCB project ZIP file and configure analysis settings
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
                Project Name
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="My PCB Project"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                EDA Tool
              </label>
              <select
                value={edaTool}
                onChange={(e) => setEdaTool(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="kicad">KiCad (Recommended)</option>
                <option value="gerber">Gerber / Generic</option>
                <option value="altium">Altium Designer</option>
                <option value="easyleda">EasyEDA</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Fabrication Profile
              </label>
              <select
                value={fabProfile}
                onChange={(e) => setFabProfile(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="cheap_cn_8mil">Cheap CN fab (6/6 mil)</option>
                <option value="local_fab_8mil">Local fab (8/8 mil)</option>
                <option value="hdi_4mil">HDI capable (4/4 mil)</option>
              </select>
              <p className="text-xs text-gray-400 mt-1">
                Choose based on your target fabrication house capabilities
              </p>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}

          {/* Submit Button */}
          <div className="mt-6 flex justify-end">
            <button
              onClick={handleStartAnalysis}
              disabled={isUploading}
              className="btn-primary flex items-center space-x-2"
            >
              <span>Start Analysis</span>
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
