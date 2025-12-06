import { useCallback, useState } from 'react'
import { Upload, FileArchive, AlertCircle } from 'lucide-react'

interface UploadZoneProps {
  onFileSelect: (file: File) => void
  isUploading: boolean
}

export default function UploadZone({ onFileSelect, isUploading }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const SUPPORTED_EXTENSIONS = [
    '.zip', '.kicad_pcb', '.kicad_sch', '.brd', '.sch', 
    '.pcbdoc', '.schdoc', '.dsn', '.gbr', '.ger', '.gtl', 
    '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gko', '.drl',
    '.xml', '.csv', '.xlsx', '.pos', '.xy'
  ]

  const validateFile = (file: File): boolean => {
    const fileName = file.name.toLowerCase()
    const isSupported = SUPPORTED_EXTENSIONS.some(ext => fileName.endsWith(ext))
    
    if (!isSupported) {
      setError('Unsupported file type. Upload ZIP, KiCad, Eagle, Altium, Gerber, or assembly files.')
      return false
    }
    
    // 500MB limit for large projects
    if (file.size > 500 * 1024 * 1024) {
      setError('File size must be less than 500MB')
      return false
    }
    
    setError(null)
    return true
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      const file = files[0]
      if (validateFile(file)) {
        onFileSelect(file)
      }
    }
  }, [onFileSelect])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const file = files[0]
      if (validateFile(file)) {
        onFileSelect(file)
      }
    }
  }

  return (
    <div className="w-full">
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
          transition-all duration-200
          ${isDragging 
            ? 'border-primary-500 bg-primary-900/20' 
            : 'border-gray-600 bg-gray-800/50 hover:border-primary-400 hover:bg-primary-900/20'
          }
          ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".zip,.kicad_pcb,.kicad_sch,.brd,.sch,.pcbdoc,.schdoc,.dsn,.gbr,.ger,.gtl,.gbl,.gts,.gbs,.drl,.xml,.csv,.xlsx,.pos,.xy"
          onChange={handleFileInput}
          disabled={isUploading}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
        
        <div className="flex flex-col items-center space-y-4">
          {isUploading ? (
            <>
              <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary-600"></div>
              <p className="text-lg font-medium text-gray-300">Uploading...</p>
            </>
          ) : (
            <>
              <div className="p-4 bg-primary-900/30 rounded-full">
                {isDragging ? (
                  <FileArchive className="h-12 w-12 text-primary-600" />
                ) : (
                  <Upload className="h-12 w-12 text-primary-600" />
                )}
              </div>
              
              <div>
                <p className="text-lg font-medium text-gray-100">
                  Drag & drop your PCB files
                </p>
                <p className="text-sm text-gray-300 mt-1">
                  ZIP archives or single files • Auto-detected
                </p>
              </div>
              
              <p className="text-xs text-gray-500">
                KiCad • Eagle • Altium • Cadence • Gerber • ODB++ • IPC-2581 • BOM/PnP
              </p>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-4 flex items-center space-x-2 text-red-300 bg-red-900/40 border border-red-700 rounded-lg p-3">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}
    </div>
  )
}
