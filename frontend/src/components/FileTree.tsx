import { useState } from 'react'
import { 
  ChevronRight, 
  ChevronDown, 
  File, 
  Folder, 
  FolderOpen,
  FileCode,
  FileText,
  Cpu,
  CircuitBoard,
  Layers,
  Package,
  Settings,
  MessageSquare,
  Info
} from 'lucide-react'

// File type to icon mapping
const FILE_TYPE_ICONS: Record<string, React.ReactNode> = {
  pcb_layout: <CircuitBoard className="h-4 w-4 text-green-400" />,
  schematic: <Cpu className="h-4 w-4 text-blue-400" />,
  gerber: <Layers className="h-4 w-4 text-purple-400" />,
  drill: <Layers className="h-4 w-4 text-orange-400" />,
  bom: <FileText className="h-4 w-4 text-yellow-400" />,
  pick_and_place: <Package className="h-4 w-4 text-pink-400" />,
  model_3d: <Package className="h-4 w-4 text-cyan-400" />,
  project: <Settings className="h-4 w-4 text-gray-400" />,
  footprint: <CircuitBoard className="h-4 w-4 text-indigo-400" />,
  symbol: <FileCode className="h-4 w-4 text-indigo-400" />,
  library: <Folder className="h-4 w-4 text-amber-400" />,
  documentation: <FileText className="h-4 w-4 text-gray-400" />,
  other: <File className="h-4 w-4 text-gray-500" />,
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

interface FileTreeProps {
  tree: FileNode
  onFileSelect?: (file: FileNode) => void
  onAddComment?: (file: FileNode) => void
  selectedPath?: string
  fileComments?: Record<string, number>  // path -> comment count
}

interface FileTreeNodeProps {
  node: FileNode
  depth: number
  onFileSelect?: (file: FileNode) => void
  onAddComment?: (file: FileNode) => void
  selectedPath?: string
  fileComments?: Record<string, number>
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function FileTreeNodeComponent({ 
  node, 
  depth, 
  onFileSelect,
  onAddComment,
  selectedPath,
  fileComments = {}
}: FileTreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(depth < 2) // Auto-expand first 2 levels
  
  const isSelected = selectedPath === node.path
  const commentCount = fileComments[node.path] || 0
  
  const getFileIcon = () => {
    if (node.is_directory) {
      return isExpanded ? (
        <FolderOpen className="h-4 w-4 text-amber-400" />
      ) : (
        <Folder className="h-4 w-4 text-amber-400" />
      )
    }
    return FILE_TYPE_ICONS[node.file_type || 'other'] || <File className="h-4 w-4 text-gray-500" />
  }
  
  const handleClick = () => {
    if (node.is_directory) {
      setIsExpanded(!isExpanded)
    } else if (onFileSelect) {
      onFileSelect(node)
    }
  }
  
  const handleCommentClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (onAddComment) {
      onAddComment(node)
    }
  }
  
  return (
    <div>
      <div
        className={`
          flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer
          hover:bg-gray-800/50 transition-colors group
          ${isSelected ? 'bg-pcbGreen/20 border border-pcbGreen/40' : ''}
        `}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleClick}
      >
        {/* Expand/collapse arrow */}
        {node.is_directory ? (
          <span className="w-4 flex-shrink-0">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-gray-500" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-500" />
            )}
          </span>
        ) : (
          <span className="w-4 flex-shrink-0" />
        )}
        
        {/* File/folder icon */}
        <span className="flex-shrink-0">{getFileIcon()}</span>
        
        {/* Name */}
        <span className={`flex-1 text-sm truncate ${isSelected ? 'text-white font-medium' : 'text-gray-300'}`}>
          {node.name}
        </span>
        
        {/* Comment indicator */}
        {commentCount > 0 && (
          <span className="flex items-center gap-1 text-xs text-blue-400">
            <MessageSquare className="h-3 w-3" />
            {commentCount}
          </span>
        )}
        
        {/* Purpose badge */}
        {!node.is_directory && node.purpose && (
          <span className="hidden group-hover:flex items-center gap-1 text-xs text-gray-500">
            <Info className="h-3 w-3" />
          </span>
        )}
        
        {/* Add comment button */}
        {!node.is_directory && onAddComment && (
          <button
            onClick={handleCommentClick}
            className="hidden group-hover:flex items-center p-1 hover:bg-gray-700 rounded"
            title="Add comment"
          >
            <MessageSquare className="h-3 w-3 text-gray-400 hover:text-blue-400" />
          </button>
        )}
        
        {/* Size */}
        {node.size_bytes !== undefined && node.size_bytes > 0 && (
          <span className="text-xs text-gray-600 flex-shrink-0">
            {formatFileSize(node.size_bytes)}
          </span>
        )}
      </div>
      
      {/* Children */}
      {node.is_directory && isExpanded && node.children && (
        <div>
          {node.children.map((child, index) => (
            <FileTreeNodeComponent
              key={`${child.path}-${index}`}
              node={child}
              depth={depth + 1}
              onFileSelect={onFileSelect}
              onAddComment={onAddComment}
              selectedPath={selectedPath}
              fileComments={fileComments}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function FileTree({ 
  tree, 
  onFileSelect, 
  onAddComment,
  selectedPath,
  fileComments = {}
}: FileTreeProps) {
  // Count total files
  const countFiles = (node: FileNode): number => {
    if (!node.is_directory) return 1
    return (node.children || []).reduce((sum, child) => sum + countFiles(child), 0)
  }
  
  const totalFiles = countFiles(tree)
  
  return (
    <div className="bg-gray-900/50 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Folder className="h-5 w-5 text-pcbGreen" />
          <span className="font-medium text-gray-200">Project Files</span>
        </div>
        <span className="text-xs text-gray-500">{totalFiles} files</span>
      </div>
      
      {/* Tree */}
      <div className="p-2 max-h-[500px] overflow-y-auto">
        {tree.children && tree.children.length > 0 ? (
          tree.children.map((child, index) => (
            <FileTreeNodeComponent
              key={`${child.path}-${index}`}
              node={child}
              depth={0}
              onFileSelect={onFileSelect}
              onAddComment={onAddComment}
              selectedPath={selectedPath}
              fileComments={fileComments}
            />
          ))
        ) : (
          <div className="text-center py-8 text-gray-500">
            <File className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No files found</p>
          </div>
        )}
      </div>
    </div>
  )
}
