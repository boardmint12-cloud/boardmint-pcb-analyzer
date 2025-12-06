import { useState } from 'react'
import { 
  MessageSquare, 
  Send, 
  X, 
  User, 
  Clock,
  Trash2,
  CheckCircle,
  AlertCircle,
  XCircle,
  HelpCircle
} from 'lucide-react'

export interface Comment {
  id: string
  comment: string
  status?: string
  created_by: string
  created_by_name: string
  created_at: string
}

interface CommentBoxProps {
  comments: Comment[]
  onAddComment: (comment: string, status?: string) => Promise<void>
  onDeleteComment?: (commentId: string) => Promise<void>
  currentUserId?: string
  placeholder?: string
  title?: string
  showStatus?: boolean
  isLoading?: boolean
}

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open', icon: HelpCircle, color: 'text-gray-400' },
  { value: 'acknowledged', label: 'Acknowledged', icon: AlertCircle, color: 'text-yellow-400' },
  { value: 'resolved', label: 'Resolved', icon: CheckCircle, color: 'text-green-400' },
  { value: 'wont_fix', label: "Won't Fix", icon: XCircle, color: 'text-red-400' },
]

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  })
}

function getStatusInfo(status: string) {
  return STATUS_OPTIONS.find(s => s.value === status) || STATUS_OPTIONS[0]
}

export default function CommentBox({
  comments,
  onAddComment,
  onDeleteComment,
  currentUserId,
  placeholder = 'Add a comment...',
  title = 'Comments',
  showStatus = false,
  isLoading = false
}: CommentBoxProps) {
  const [newComment, setNewComment] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('open')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newComment.trim() || isSubmitting) return
    
    setIsSubmitting(true)
    try {
      await onAddComment(newComment.trim(), showStatus ? selectedStatus : undefined)
      setNewComment('')
      setSelectedStatus('open')
    } catch (error) {
      console.error('Failed to add comment:', error)
    } finally {
      setIsSubmitting(false)
    }
  }
  
  const handleDelete = async (commentId: string) => {
    if (!onDeleteComment || deletingId) return
    
    setDeletingId(commentId)
    try {
      await onDeleteComment(commentId)
    } catch (error) {
      console.error('Failed to delete comment:', error)
    } finally {
      setDeletingId(null)
    }
  }
  
  return (
    <div className="bg-gray-900/50 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800">
        <MessageSquare className="h-5 w-5 text-blue-400" />
        <span className="font-medium text-gray-200">{title}</span>
        {comments.length > 0 && (
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
            {comments.length}
          </span>
        )}
      </div>
      
      {/* Comments list */}
      <div className="max-h-[300px] overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400" />
          </div>
        ) : comments.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No comments yet</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {comments.map((comment) => {
              const statusInfo = getStatusInfo(comment.status || 'open')
              const StatusIcon = statusInfo.icon
              const canDelete = currentUserId === comment.created_by
              
              return (
                <div key={comment.id} className="p-4 hover:bg-gray-800/30 transition-colors group">
                  {/* Header */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center">
                        <User className="h-3 w-3 text-gray-400" />
                      </div>
                      <span className="text-sm font-medium text-gray-300">
                        {comment.created_by_name}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <Clock className="h-3 w-3" />
                        {formatDate(comment.created_at)}
                      </span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {/* Status badge */}
                      {showStatus && comment.status && (
                        <span className={`flex items-center gap-1 text-xs ${statusInfo.color}`}>
                          <StatusIcon className="h-3 w-3" />
                          {statusInfo.label}
                        </span>
                      )}
                      
                      {/* Delete button */}
                      {canDelete && onDeleteComment && (
                        <button
                          onClick={() => handleDelete(comment.id)}
                          disabled={deletingId === comment.id}
                          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-900/50 rounded transition-all"
                          title="Delete comment"
                        >
                          {deletingId === comment.id ? (
                            <div className="animate-spin h-3 w-3 border border-red-400 border-t-transparent rounded-full" />
                          ) : (
                            <Trash2 className="h-3 w-3 text-red-400" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* Comment text */}
                  <p className="text-sm text-gray-300 whitespace-pre-wrap">
                    {comment.comment}
                  </p>
                </div>
              )
            })}
          </div>
        )}
      </div>
      
      {/* Add comment form */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-800">
        <div className="flex flex-col gap-3">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder={placeholder}
            rows={2}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
          />
          
          <div className="flex items-center justify-between">
            {/* Status selector */}
            {showStatus && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Status:</span>
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            
            {!showStatus && <div />}
            
            {/* Submit button */}
            <button
              type="submit"
              disabled={!newComment.trim() || isSubmitting}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              {isSubmitting ? (
                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              <span>Comment</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}

// Compact inline comment button for file tree
interface InlineCommentButtonProps {
  onClick: () => void
  commentCount?: number
}

export function InlineCommentButton({ onClick, commentCount = 0 }: InlineCommentButtonProps) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-blue-400 hover:bg-gray-800 rounded transition-colors"
    >
      <MessageSquare className="h-3 w-3" />
      {commentCount > 0 && <span>{commentCount}</span>}
    </button>
  )
}

// Modal wrapper for comments
interface CommentModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
}

export function CommentModal({ isOpen, onClose, title, children }: CommentModalProps) {
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-gray-900 rounded-xl border border-gray-800 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <h3 className="font-medium text-gray-200">{title}</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-800 rounded transition-colors"
          >
            <X className="h-5 w-5 text-gray-400" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-4">
          {children}
        </div>
      </div>
    </div>
  )
}
