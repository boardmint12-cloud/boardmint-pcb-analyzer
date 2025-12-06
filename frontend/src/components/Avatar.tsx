import { cn } from '@/lib/utils'

interface AvatarProps {
  name: string
  avatarUrl?: string | null
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

// Generate a consistent color based on name
function getAvatarColor(name: string): string {
  const colors = [
    'bg-blue-600',
    'bg-green-600',
    'bg-purple-600',
    'bg-orange-600',
    'bg-pink-600',
    'bg-cyan-600',
    'bg-indigo-600',
    'bg-teal-600',
    'bg-rose-600',
    'bg-amber-600',
  ]
  
  // Hash the name to get a consistent index
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  return colors[Math.abs(hash) % colors.length]
}

// Get initials from name
function getInitials(name: string): string {
  if (!name) return '?'
  
  const parts = name.trim().split(' ')
  if (parts.length === 1) {
    return parts[0].charAt(0).toUpperCase()
  }
  
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase()
}

const sizeClasses = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
}

export default function Avatar({ name, avatarUrl, size = 'md', className }: AvatarProps) {
  const sizeClass = sizeClasses[size]
  
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className={cn(
          'rounded-full object-cover ring-2 ring-gray-800',
          sizeClass,
          className
        )}
      />
    )
  }
  
  const initials = getInitials(name)
  const bgColor = getAvatarColor(name)
  
  return (
    <div
      className={cn(
        'rounded-full flex items-center justify-center font-medium text-white ring-2 ring-gray-800',
        bgColor,
        sizeClass,
        className
      )}
      title={name}
    >
      {initials}
    </div>
  )
}

// Avatar group for showing multiple contributors
interface AvatarGroupProps {
  contributors: Array<{
    user_id: string
    full_name: string
    avatar_url?: string | null
  }>
  maxVisible?: number
  size?: 'sm' | 'md' | 'lg'
}

export function AvatarGroup({ contributors, maxVisible = 3, size = 'md' }: AvatarGroupProps) {
  const visible = contributors.slice(0, maxVisible)
  const remaining = contributors.length - maxVisible
  
  const overlapClass = {
    sm: '-ml-2',
    md: '-ml-3',
    lg: '-ml-4',
  }
  
  const remainingSizeClass = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-10 h-10 text-sm',
    lg: 'w-12 h-12 text-base',
  }
  
  return (
    <div className="flex items-center">
      {visible.map((contributor, index) => (
        <div 
          key={contributor.user_id} 
          className={index > 0 ? overlapClass[size] : ''}
          style={{ zIndex: visible.length - index }}
        >
          <Avatar
            name={contributor.full_name}
            avatarUrl={contributor.avatar_url}
            size={size}
          />
        </div>
      ))}
      
      {remaining > 0 && (
        <div 
          className={cn(
            'rounded-full flex items-center justify-center font-medium bg-gray-700 text-white ring-2 ring-gray-800',
            remainingSizeClass[size],
            overlapClass[size]
          )}
          title={`+${remaining} more contributors`}
        >
          +{remaining}
        </div>
      )}
    </div>
  )
}
