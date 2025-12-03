import { ChevronRight, Zap, Radio, Battery, ShoppingCart, Wrench } from 'lucide-react'
import { formatCategoryName } from '@/lib/utils'

interface CategoryCardProps {
  category: string
  criticalCount: number
  warningCount: number
  infoCount: number
  onClick: () => void
}

export default function CategoryCard({
  category,
  criticalCount,
  warningCount,
  infoCount,
  onClick,
}: CategoryCardProps) {
  const icons: Record<string, any> = {
    mains_safety: Zap,
    bus_interfaces: Radio,
    power_smps: Battery,
    bom: ShoppingCart,
    assembly_test: Wrench,
  }

  const Icon = icons[category] || Zap
  const totalIssues = criticalCount + warningCount + infoCount

  return (
    <button
      onClick={onClick}
      className="w-full card hover:shadow-md transition-shadow duration-200 text-left group"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-4 flex-1">
          <div className="p-3 bg-primary-900/30 rounded-lg">
            <Icon className="h-6 w-6 text-primary-500" />
          </div>
          
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-100 mb-2">
              {formatCategoryName(category)}
            </h3>
            
            <div className="flex items-center space-x-4 text-sm">
              {criticalCount > 0 && (
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span>
                  <span className="text-gray-300">{criticalCount} Critical</span>
                </span>
              )}
              {warningCount > 0 && (
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  <span className="text-gray-300">{warningCount} Warning</span>
                </span>
              )}
              {infoCount > 0 && (
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  <span className="text-gray-300">{infoCount} Info</span>
                </span>
              )}
            </div>
            
            <p className="text-sm text-gray-400 mt-2">
              {totalIssues} {totalIssues === 1 ? 'issue' : 'issues'} found
            </p>
          </div>
        </div>
        
        <ChevronRight className="h-6 w-6 text-gray-400 group-hover:text-primary-600 transition-colors flex-shrink-0" />
      </div>
    </button>
  )
}
