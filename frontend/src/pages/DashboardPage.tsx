import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAnalysisResults, downloadPDFReport, AnalysisResults } from '@/lib/api'
import RiskBadge from '@/components/RiskBadge'
import CategoryCard from '@/components/CategoryCard'
import IssueCard from '@/components/IssueCard'
import { Loader2, Download, ArrowLeft, Layers, Ruler, Cpu, Zap, Sparkles, Lightbulb, CheckCircle2, Package } from 'lucide-react'
import { formatCategoryName } from '@/lib/utils'

export default function DashboardPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [results, setResults] = useState<AnalysisResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  useEffect(() => {
    if (!jobId) return

    let active = true // Track if component is mounted
    let timeoutId: NodeJS.Timeout | null = null

    const fetchResults = async () => {
      if (!active) return // Don't fetch if unmounted

      try {
        const data = await getAnalysisResults(jobId)
        
        // Check again after async operation
        if (!active) return
        
        setResults(data)
        setLoading(false)

        // If still running, schedule next poll using setTimeout (not setInterval)
        if (data.status === 'running' || data.status === 'pending') {
          timeoutId = setTimeout(fetchResults, 3000)
        }
      } catch (err: any) {
        if (active) {
          setError('Failed to load analysis results')
          setLoading(false)
        }
      }
    }

    fetchResults()

    // Cleanup function
    return () => {
      active = false // Prevent state updates after unmount
      if (timeoutId) {
        clearTimeout(timeoutId) // Cancel pending poll
      }
    }
  }, [jobId]) // Only re-run when jobId changes

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <Loader2 className="h-16 w-16 text-primary-600 animate-spin mb-4" />
        <p className="text-lg font-medium text-gray-700">Analyzing PCB project...</p>
        <p className="text-sm text-gray-500 mt-2">{results?.progress || 'Starting analysis'}</p>
      </div>
    )
  }

  if (error || !results) {
    return (
      <div className="card max-w-2xl mx-auto text-center py-16">
        <p className="text-lg font-medium text-red-600 mb-4">{error || 'Analysis not found'}</p>
        <button onClick={() => navigate('/')} className="btn-primary">
          <ArrowLeft className="inline-block h-5 w-5 mr-2" />
          Back to Home
        </button>
      </div>
    )
  }

  const issueCategories = Object.keys(results.issues_by_category)

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/projects')}
            className="text-pcbGreen hover:text-pcbGreen-light font-medium mb-2 inline-flex items-center"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Projects
          </button>
          <h1 className="text-3xl font-bold text-gray-100">Analysis Results</h1>
        </div>
        <button
          onClick={() => window.open(downloadPDFReport(jobId!), '_blank')}
          className="btn-primary flex items-center space-x-2"
        >
          <Download className="h-5 w-5" />
          <span>Download Report</span>
        </button>
      </div>

      {/* Summary Cards Grid */}
      <div className="grid lg:grid-cols-3 gap-6 mb-8">
        {/* Risk & Issues Card */}
        <div className="lg:col-span-2 card">
          <div className="mb-4">
            <RiskBadge riskLevel={results.risk_level} />
          </div>
          <div className="grid grid-cols-3 gap-6">
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <p className="text-sm text-gray-400 mb-1">Critical Issues</p>
              <p className="text-4xl font-bold text-red-500">{results.summary.critical}</p>
            </div>
            <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-500/20">
              <p className="text-sm text-gray-400 mb-1">Warnings</p>
              <p className="text-4xl font-bold text-orange-500">{results.summary.warning}</p>
            </div>
            <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
              <p className="text-sm text-gray-400 mb-1">Info</p>
              <p className="text-4xl font-bold text-blue-500">{results.summary.info}</p>
            </div>
          </div>
        </div>

        {/* Board Info Card */}
        {results.board_info && (
          <div className="card bg-gradient-to-br from-pcbGreen/10 to-pcbGreen/5 border-pcbGreen/30">
            <div className="flex items-center mb-4">
              <div className="p-2 bg-pcbGreen/20 rounded-lg mr-3">
                <Cpu className="h-6 w-6 text-pcbGreen" />
              </div>
              <h3 className="text-lg font-semibold text-gray-100">Board Specs</h3>
            </div>
            
            <div className="space-y-3">
              {/* Board Dimensions */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Ruler className="h-4 w-4 text-pcbGreen/70" />
                  <span className="text-sm text-gray-400">Dimensions</span>
                </div>
                <span className="text-sm font-semibold text-gray-100">
                  {results.board_info.size_x} × {results.board_info.size_y} mm
                </span>
              </div>

              {/* Layer Count */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Layers className="h-4 w-4 text-pcbGreen/70" />
                  <span className="text-sm text-gray-400">Layers</span>
                </div>
                <span className="text-sm font-semibold text-gray-100">
                  {results.board_info.layer_count} Layer{results.board_info.layer_count !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Min Track Width (if available) */}
              {results.board_info.min_track_width && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Zap className="h-4 w-4 text-pcbGreen/70" />
                    <span className="text-sm text-gray-400">Min Track</span>
                  </div>
                  <span className="text-sm font-semibold text-gray-100">
                    {results.board_info.min_track_width} mm
                  </span>
                </div>
              )}

              {/* Area */}
              <div className="flex items-center justify-between pt-2 border-t border-pcbGreen/20">
                <span className="text-xs text-gray-500">Board Area</span>
                <span className="text-xs font-medium text-pcbGreen">
                  {(results.board_info.size_x * results.board_info.size_y).toFixed(2)} mm²
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* AI Board Summary */}
      {results.board_summary && (
        <div className="card bg-gradient-to-br from-purple-900/20 to-blue-900/20 border-purple-500/30 mb-8">
          <div className="flex items-center mb-4">
            <div className="p-2 bg-purple-500/20 rounded-lg mr-3">
              <Sparkles className="h-6 w-6 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-100">AI Board Analysis</h3>
          </div>
          
          <div className="space-y-4">
            {/* Purpose */}
            <div>
              <div className="flex items-center space-x-2 mb-2">
                <Lightbulb className="h-4 w-4 text-yellow-400" />
                <h4 className="text-sm font-semibold text-gray-200">Purpose</h4>
              </div>
              <p className="text-base text-gray-300 leading-relaxed">{results.board_summary.purpose}</p>
            </div>

            {/* Description/How it works */}
            {results.board_summary.description && (
              <div>
                <div className="flex items-center space-x-2 mb-2">
                  <Cpu className="h-4 w-4 text-blue-400" />
                  <h4 className="text-sm font-semibold text-gray-200">How It Works</h4>
                </div>
                <p className="text-sm text-gray-300 leading-relaxed">{results.board_summary.description}</p>
              </div>
            )}

            {/* Key Features */}
            {results.board_summary.key_features && results.board_summary.key_features.length > 0 && (
              <div>
                <div className="flex items-center space-x-2 mb-2">
                  <CheckCircle2 className="h-4 w-4 text-green-400" />
                  <h4 className="text-sm font-semibold text-gray-200">Key Features</h4>
                </div>
                <ul className="space-y-1">
                  {results.board_summary.key_features.map((feature, idx) => (
                    <li key={idx} className="text-sm text-gray-300 flex items-start">
                      <span className="text-green-400 mr-2">•</span>
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Main Components */}
            {results.board_summary.main_components && results.board_summary.main_components.length > 0 && (
              <div>
                <div className="flex items-center space-x-2 mb-2">
                  <Package className="h-4 w-4 text-orange-400" />
                  <h4 className="text-sm font-semibold text-gray-200">Main Components</h4>
                </div>
                <div className="flex flex-wrap gap-2">
                  {results.board_summary.main_components.map((component, idx) => (
                    <span
                      key={idx}
                      className="text-xs bg-gray-800/50 text-gray-300 px-3 py-1 rounded-full border border-gray-700"
                    >
                      {component}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Design Notes */}
            {results.board_summary.design_notes && (
              <div className="pt-3 border-t border-purple-500/20">
                <p className="text-xs text-purple-300 italic">💡 {results.board_summary.design_notes}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Category Selection / Issues */}
      {!selectedCategory ? (
        <>
          <h2 className="text-2xl font-bold text-gray-100 mb-6">Issues by Category</h2>
          <div className="grid md:grid-cols-2 gap-6">
            {issueCategories.map((category) => {
              const issues = results.issues_by_category[category]
              const criticalCount = issues.filter(i => i.severity === 'critical').length
              const warningCount = issues.filter(i => i.severity === 'warning').length
              const infoCount = issues.filter(i => i.severity === 'info').length

              return (
                <CategoryCard
                  key={category}
                  category={category}
                  criticalCount={criticalCount}
                  warningCount={warningCount}
                  infoCount={infoCount}
                  onClick={() => setSelectedCategory(category)}
                />
              )
            })}
          </div>
        </>
      ) : (
        <>
          <div className="mb-6">
            <button
              onClick={() => setSelectedCategory(null)}
              className="text-pcbGreen hover:text-pcbGreen-light font-medium mb-2 inline-flex items-center"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Categories
            </button>
            <h2 className="text-2xl font-bold text-gray-100">
              {formatCategoryName(selectedCategory)}
            </h2>
            <p className="text-gray-400">
              {results.issues_by_category[selectedCategory].length} {results.issues_by_category[selectedCategory].length === 1 ? 'issue' : 'issues'} found
            </p>
          </div>

          <div className="space-y-4">
            {results.issues_by_category[selectedCategory].map((issue) => (
              <IssueCard key={issue.id} issue={issue} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
