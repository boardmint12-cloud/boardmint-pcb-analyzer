import { AlertCircle, AlertTriangle, Info, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { Issue } from '@/lib/api'
import { getSeverityColor } from '@/lib/utils'

interface IssueCardProps {
  issue: Issue
}

export default function IssueCard({ issue }: IssueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const severityIcons = {
    critical: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  }

  const Icon = severityIcons[issue.severity]
  const colorClass = getSeverityColor(issue.severity)

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1">
          <div className={`p-2 rounded-lg ${colorClass}`}>
            <Icon className="h-5 w-5" />
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 mb-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${colorClass}`}>
                {issue.issue_code}
              </span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded uppercase ${colorClass}`}>
                {issue.severity}
              </span>
            </div>
            
            <h4 className="text-base font-semibold text-gray-100 mb-2">
              {issue.title}
            </h4>
            
            <p className="text-sm text-gray-300 mb-3">
              {issue.description}
            </p>
            
            {isExpanded && (
              <div className="space-y-3 mt-4 pt-4 border-t border-gray-700">
                <div>
                  <h5 className="text-sm font-semibold text-gray-100 mb-1">
                    Suggested Fix:
                  </h5>
                  <p className="text-sm text-gray-300 whitespace-pre-line">
                    {issue.suggested_fix}
                  </p>
                </div>
                
                {issue.affected_components && issue.affected_components.length > 0 && (
                  <div>
                    <h5 className="text-sm font-semibold text-gray-100 mb-1">
                      Affected Components:
                    </h5>
                    <div className="flex flex-wrap gap-1">
                      {issue.affected_components.slice(0, 10).map((comp) => (
                        <span
                          key={comp}
                          className="text-xs bg-gray-700 text-gray-100 px-2 py-1 rounded"
                        >
                          {comp}
                        </span>
                      ))}
                      {issue.affected_components.length > 10 && (
                        <span className="text-xs text-gray-400 px-2 py-1">
                          +{issue.affected_components.length - 10} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
                
                {issue.affected_nets && issue.affected_nets.length > 0 && (
                  <div>
                    <h5 className="text-sm font-semibold text-gray-100 mb-1">
                      Affected Nets:
                    </h5>
                    <div className="flex flex-wrap gap-1">
                      {issue.affected_nets.slice(0, 10).map((net) => (
                        <span
                          key={net}
                          className="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded border border-blue-700"
                        >
                          {net}
                        </span>
                      ))}
                      {issue.affected_nets.length > 10 && (
                        <span className="text-xs text-gray-400 px-2 py-1">
                          +{issue.affected_nets.length - 10} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="ml-4 p-2 hover:bg-gray-800 rounded-lg transition-colors flex-shrink-0"
        >
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          )}
        </button>
      </div>
    </div>
  )
}
