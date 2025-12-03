import { AlertCircle, AlertTriangle, CheckCircle } from 'lucide-react'
import { getRiskLevelColor } from '@/lib/utils'

interface RiskBadgeProps {
  riskLevel: 'low' | 'moderate' | 'high'
  size?: 'sm' | 'lg'
}

export default function RiskBadge({ riskLevel, size = 'lg' }: RiskBadgeProps) {
  const colorClass = getRiskLevelColor(riskLevel)
  
  const sizeClasses = size === 'sm' 
    ? 'text-sm px-3 py-1' 
    : 'text-lg px-6 py-3'
  
  const iconSize = size === 'sm' ? 'h-4 w-4' : 'h-6 w-6'

  return (
    <div className={`inline-flex items-center space-x-2 rounded-lg border font-semibold ${colorClass} ${sizeClasses}`}>
      {riskLevel === 'low' && <CheckCircle className={iconSize} />}
      {riskLevel === 'moderate' && <AlertTriangle className={iconSize} />}
      {riskLevel === 'high' && <AlertCircle className={iconSize} />}
      <span className="capitalize">{riskLevel} Risk</span>
    </div>
  )
}
