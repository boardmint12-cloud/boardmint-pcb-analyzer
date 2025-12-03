import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind CSS classes
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format date to human readable string
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Get severity color class
 */
export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'text-red-300 bg-red-900/40 border border-red-700/50'
    case 'warning':
      return 'text-orange-300 bg-orange-900/40 border border-orange-700/50'
    case 'info':
      return 'text-blue-300 bg-blue-900/40 border border-blue-700/50'
    default:
      return 'text-gray-300 bg-gray-800/40 border border-gray-700/50'
  }
}

/**
 * Get risk level color
 */
export function getRiskLevelColor(riskLevel: string): string {
  switch (riskLevel) {
    case 'high':
      return 'text-red-300 bg-red-900/40 border-red-700'
    case 'moderate':
      return 'text-orange-300 bg-orange-900/40 border-orange-700'
    case 'low':
      return 'text-green-300 bg-green-900/40 border-green-700'
    default:
      return 'text-gray-300 bg-gray-800/40 border-gray-700'
  }
}

/**
 * Format category name
 */
export function formatCategoryName(category: string): string {
  return category
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
