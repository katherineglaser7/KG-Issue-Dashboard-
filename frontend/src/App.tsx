import { useState, useEffect, useCallback, useRef } from 'react'
import { ChevronDown, ChevronUp, Circle, Plus, MoreHorizontal, Filter, HelpCircle, ExternalLink, X, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface JobStatus {
  id: string
  ticket_id: number
  status: 'running' | 'completed' | 'failed'
  current_step: string | null
  steps_completed: number
  total_steps: number
  error_message: string | null
  worktree_path: string | null
  branch_name: string | null
}

interface JobData {
  [key: number]: {
    job: JobStatus | null
    isPolling: boolean
    error: string | null
  }
}

interface ScoreFactors {
  score: number
  factors: string[]
}

interface ConfidenceBreakdown {
  requirement_clarity: ScoreFactors
  blast_radius: ScoreFactors
  system_sensitivity: ScoreFactors
  testability: ScoreFactors
}

interface ConfidenceScore {
  total: number
  breakdown: ConfidenceBreakdown
}

interface TicketAnalysis {
  root_issue: string
  action_plan: string[]
  confidence_score: ConfidenceScore
}

interface Ticket {
  id: number
  number: number
  title: string
  body: string | null
  status: 'new' | 'scoped' | 'in_progress' | 'review' | 'complete' | string
  labels: string[]
  created_at: string
  updated_at: string
  html_url: string
  analysis: TicketAnalysis | null
  pr_number: number | null
  pr_url: string | null
  branch_name: string | null
  job: JobStatus | null
}

interface ScopeData {
  [key: number]: {
    loading: boolean
    analysis: TicketAnalysis | null
    expanded: boolean
  }
}

function ConfidenceTooltip({ breakdown }: { breakdown: ConfidenceBreakdown }) {
  const [isVisible, setIsVisible] = useState(false)

  const dimensions = [
    { key: 'requirement_clarity', label: 'Requirement Clarity' },
    { key: 'blast_radius', label: 'Blast Radius' },
    { key: 'system_sensitivity', label: 'System Sensitivity' },
    { key: 'testability', label: 'Testability' },
  ] as const

  return (
    <div className="relative inline-block">
      <button
        className="ml-1 text-zinc-500 hover:text-zinc-300 transition-colors"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>
      {isVisible && (
        <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 w-72 bg-zinc-900 border border-zinc-700 rounded-lg p-3 shadow-xl">
          <div className="space-y-3">
            {dimensions.map(({ key, label }) => {
              const dimension = breakdown[key]
              return (
                <div key={key}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-medium text-zinc-300">{label}</span>
                    <span className="text-xs text-zinc-400">{dimension.score}/25</span>
                  </div>
                  {dimension.factors.length > 0 ? (
                    <ul className="space-y-0.5">
                      {dimension.factors.map((factor, idx) => {
                        const isPositive = factor.includes('(+')
                        return (
                          <li
                            key={idx}
                            className={`text-xs ${isPositive ? 'text-green-400' : 'text-red-400'}`}
                          >
                            {factor}
                          </li>
                        )
                      })}
                    </ul>
                  ) : (
                    <span className="text-xs text-zinc-500 italic">No factors</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function AnalysisDisplay({ analysis, compact = false }: { analysis: TicketAnalysis; compact?: boolean }) {
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400'
    if (score >= 60) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div className="bg-zinc-900/50 rounded-md p-3 space-y-3">
      {!compact && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-zinc-400">Confidence Score</span>
          <div className="flex items-center">
            <span className={`text-lg font-bold ${getScoreColor(analysis.confidence_score.total)}`}>
              {analysis.confidence_score.total}/100
            </span>
            <ConfidenceTooltip breakdown={analysis.confidence_score.breakdown} />
          </div>
        </div>
      )}

      <div>
        <span className="text-xs text-zinc-400 block mb-1">Root Issue</span>
        <p className="text-xs text-zinc-300">{analysis.root_issue}</p>
      </div>

      <div>
        <span className="text-xs text-zinc-400 block mb-1">Action Plan</span>
        <ul className="space-y-1">
          {analysis.action_plan.map((step, idx) => (
            <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2">
              <span className="text-zinc-500">{idx + 1}.</span>
              {step}
            </li>
          ))}
        </ul>
      </div>

      {!compact && (
        <div className="space-y-2 pt-2 border-t border-zinc-700">
          <span className="text-xs text-zinc-400 block">Score Breakdown</span>
          {Object.entries(analysis.confidence_score.breakdown).map(([key, value]) => {
            const labels: Record<string, string> = {
              requirement_clarity: 'Requirement Clarity',
              blast_radius: 'Blast Radius',
              system_sensitivity: 'System Sensitivity',
              testability: 'Testability',
            }
            return (
              <div key={key} className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">{labels[key] || key}</span>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        value.score >= 20 ? 'bg-green-500' : 
                        value.score >= 15 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${(value.score / 25) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-zinc-400 w-8 text-right">{value.score}/25</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function TicketCard({ 
  ticket, 
  scopeData, 
  onScope,
  columnType,
  jobData,
  onExecute,
  onCancel,
  onComplete,
}: { 
  ticket: Ticket
  scopeData: ScopeData
  onScope: (ticketNumber: number) => void
  columnType: 'new' | 'scoped' | 'review' | 'complete'
  jobData: JobData
  onExecute: (ticketNumber: number) => void
  onCancel: (ticketNumber: number) => void
  onComplete: (ticketNumber: number) => void
}){
  const scope = scopeData[ticket.number]
  const isExpanded = scope?.expanded || false
  const isLoading = scope?.loading || false
  const analysis = scope?.analysis || ticket.analysis || null
  const job = jobData[ticket.number]?.job

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400'
    if (score >= 60) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getCardStyles = () => {
    if (ticket.status === 'in_progress' || job?.status === 'running') {
      return 'bg-zinc-800/50 border-yellow-500 bg-yellow-500/10'
    }
    if (job?.status === 'failed') {
      return 'bg-zinc-800/50 border-red-500 bg-red-500/10'
    }
    if (columnType === 'review') {
      return 'bg-zinc-800/50 border-green-500 bg-green-500/10'
    }
    if (columnType === 'complete') {
      return 'bg-zinc-800/50 border-green-700 bg-green-700/5'
    }
    return 'bg-zinc-800/50 border-zinc-700'
  }

  const getBadge = () => {
    if (ticket.status === 'in_progress' || job?.status === 'running') {
      return <span className="text-xs text-yellow-400 bg-yellow-900/50 px-1.5 py-0.5 rounded">IN PROGRESS</span>
    }
    if (job?.status === 'failed') {
      return <span className="text-xs text-red-400 bg-red-900/50 px-1.5 py-0.5 rounded">FAILED</span>
    }
    if (columnType === 'scoped' && ticket.status === 'scoped') {
      return <span className="text-xs text-zinc-400 bg-zinc-800 px-1.5 py-0.5 rounded">SCOPED</span>
    }
    if (columnType === 'review') {
      return <span className="text-xs text-green-400 bg-green-900/50 px-1.5 py-0.5 rounded">PR READY</span>
    }
    if (columnType === 'complete') {
      return <span className="text-xs text-green-500 bg-green-900/30 px-1.5 py-0.5 rounded">IMPLEMENTED</span>
    }
    return null
  }

  return (
    <Card className={`${getCardStyles()} p-3 mb-2 hover:border-zinc-500 transition-colors`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {getBadge() || (
            <>
              <Circle className="w-4 h-4 text-zinc-500" strokeDasharray="4 2" />
              <span className="text-xs text-zinc-500">New</span>
            </>
          )}
        </div>
        <MoreHorizontal className="w-4 h-4 text-zinc-500 cursor-pointer hover:text-zinc-300" />
      </div>
      <a 
        href={ticket.html_url} 
        target="_blank" 
        rel="noopener noreferrer"
        className="block mt-2 text-sm text-zinc-200 hover:text-white"
      >
        {ticket.title}
      </a>

      {ticket.labels.length > 0 && columnType === 'new' && (
        <div className="flex flex-wrap gap-1 mt-2">
          {ticket.labels.map((label) => (
            <span key={label} className="text-xs text-zinc-400 bg-zinc-700/50 px-1.5 py-0.5 rounded">
              {label}
            </span>
          ))}
        </div>
      )}

      {columnType === 'new' && (
        <Collapsible open={isExpanded}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 w-full justify-between text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/50"
              onClick={() => onScope(ticket.number)}
            >
              <span>Scope</span>
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            {isLoading ? (
              <div className="text-xs text-zinc-500 text-center py-2">
                Analyzing...
              </div>
            ) : analysis ? (
              <AnalysisDisplay analysis={analysis} />
            ) : null}
          </CollapsibleContent>
        </Collapsible>
      )}

      {columnType === 'scoped' && (
        <div className="mt-3">
          {analysis && (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-400">Confidence</span>
                <div className="flex items-center">
                  <span className={`text-sm font-bold ${getScoreColor(analysis.confidence_score.total)}`}>
                    {analysis.confidence_score.total}/100
                  </span>
                  <ConfidenceTooltip breakdown={analysis.confidence_score.breakdown} />
                </div>
              </div>
              
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-between text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/50"
                  >
                    <span>View Analysis</span>
                    <ChevronDown className="w-4 h-4" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-2">
                  <AnalysisDisplay analysis={analysis} compact />
                </CollapsibleContent>
              </Collapsible>
            </>
          )}

          {(ticket.status === 'in_progress' || job?.status === 'running') && job && (
            <div className="mt-3 p-2 bg-yellow-900/20 rounded border border-yellow-500/30">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-yellow-400 animate-spin" />
                  <span className="text-xs text-yellow-400">
                    Step {job.steps_completed + 1}/{job.total_steps}
                  </span>
                </div>
                <button
                  onClick={() => onCancel(ticket.number)}
                  className="text-xs text-zinc-400 hover:text-red-400 flex items-center gap-1"
                >
                  <X className="w-3 h-3" />
                  Cancel
                </button>
              </div>
              <p className="text-xs text-zinc-300">{job.current_step || 'Starting...'}</p>
              {(job.branch_name || ticket.branch_name) && (
                <p className="text-xs text-zinc-500 mt-1">Branch: {job.branch_name || ticket.branch_name}</p>
              )}
            </div>
          )}

          {job?.status === 'failed' && (
            <div className="mt-3 p-2 bg-red-900/20 rounded border border-red-500/30">
              <p className="text-xs text-red-400 mb-2">{job.error_message || 'Job failed'}</p>
              <Button
                variant="outline"
                size="sm"
                className="w-full text-xs border-red-500 text-red-400 hover:bg-red-500/10"
                onClick={() => onExecute(ticket.number)}
              >
                Retry
              </Button>
            </div>
          )}

          {ticket.status === 'scoped' && !job?.status && (
            <Button
              variant="outline"
              size="sm"
              className="mt-2 w-full text-xs border-blue-500 text-blue-400 hover:bg-blue-500/10"
              onClick={() => onExecute(ticket.number)}
            >
              Action
            </Button>
          )}
        </div>
      )}

      {columnType === 'review' && (
        <div className="mt-3 space-y-2">
          {ticket.branch_name && (
            <p className="text-xs text-zinc-500">Branch: {ticket.branch_name}</p>
          )}
          {ticket.pr_url && (
            <a
              href={ticket.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full py-2 text-xs text-green-400 bg-green-900/30 rounded hover:bg-green-900/50 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open PR #{ticket.pr_number}
            </a>
          )}
          <button
            onClick={() => onComplete(ticket.number)}
            className="w-full py-1.5 text-xs text-zinc-400 hover:text-green-400 hover:bg-green-900/20 rounded transition-colors"
          >
            Mark Complete
          </button>
        </div>
      )}

      {columnType === 'complete' && (
        <div className="mt-3">
          {ticket.branch_name && (
            <p className="text-xs text-zinc-500">Branch: {ticket.branch_name}</p>
          )}
          {ticket.pr_url && (
            <a
              href={ticket.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              View PR #{ticket.pr_number}
            </a>
          )}
        </div>
      )}
    </Card>
  )
}

function Column({ 
  title, 
  count, 
  tickets, 
  scopeData, 
  onScope,
  columnType,
  jobData,
  onExecute,
  onCancel,
  onComplete,
}: { 
  title: string
  count: number
  tickets: Ticket[]
  scopeData: ScopeData
  onScope: (ticketNumber: number) => void
  columnType: 'new' | 'scoped' | 'review' | 'complete'
  jobData: JobData
  onExecute: (ticketNumber: number) => void
  onCancel: (ticketNumber: number) => void
  onComplete: (ticketNumber: number) => void
}){
  return (
    <div className="flex-1 min-w-72">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium text-zinc-300">{title}</h2>
          <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full">
            {count}
          </span>
        </div>
        <MoreHorizontal className="w-4 h-4 text-zinc-500 cursor-pointer hover:text-zinc-300" />
      </div>
      <div className="space-y-2">
        {tickets.map((ticket) => (
          <TicketCard 
            key={ticket.id} 
            ticket={ticket} 
            scopeData={scopeData}
            onScope={onScope}
            columnType={columnType}
            jobData={jobData}
            onExecute={onExecute}
            onCancel={onCancel}
            onComplete={onComplete}
          />
        ))}
      </div>
    </div>
  )
}

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scopeData, setScopeData] = useState<ScopeData>({})
  const [jobData, setJobData] = useState<JobData>({})
  const pollingIntervals = useRef<{ [key: number]: NodeJS.Timeout }>({})

  useEffect(() => {
    fetchTickets()
    return () => {
      Object.values(pollingIntervals.current).forEach(clearInterval)
    }
  }, [])

  const fetchTickets = async () => {
    try {
      const response = await fetch(`${API_URL}/api/tickets`)
      if (!response.ok) {
        throw new Error('Failed to fetch tickets')
      }
      const data = await response.json()
      setTickets(data.tickets)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const startPolling = useCallback((ticketNumber: number) => {
    if (pollingIntervals.current[ticketNumber]) {
      clearInterval(pollingIntervals.current[ticketNumber])
    }

    const poll = async () => {
      try {
        const response = await fetch(`${API_URL}/api/tickets/${ticketNumber}/job`)
        if (!response.ok) {
          throw new Error('Failed to fetch job status')
        }
        const job: JobStatus = await response.json()
        
        setJobData(prev => ({
          ...prev,
          [ticketNumber]: { job, isPolling: true, error: null }
        }))

        if (job.status === 'completed') {
          clearInterval(pollingIntervals.current[ticketNumber])
          delete pollingIntervals.current[ticketNumber]
          setJobData(prev => ({
            ...prev,
            [ticketNumber]: { ...prev[ticketNumber], isPolling: false }
          }))
          fetchTickets()
        } else if (job.status === 'failed') {
          clearInterval(pollingIntervals.current[ticketNumber])
          delete pollingIntervals.current[ticketNumber]
          setJobData(prev => ({
            ...prev,
            [ticketNumber]: { ...prev[ticketNumber], isPolling: false }
          }))
        }
      } catch (err) {
        setJobData(prev => ({
          ...prev,
          [ticketNumber]: { 
            job: prev[ticketNumber]?.job || null, 
            isPolling: false, 
            error: err instanceof Error ? err.message : 'Polling error' 
          }
        }))
      }
    }

    poll()
    pollingIntervals.current[ticketNumber] = setInterval(poll, 2000)
  }, [])

  const handleExecute = async (ticketNumber: number) => {
    try {
      setJobData(prev => ({
        ...prev,
        [ticketNumber]: { job: null, isPolling: true, error: null }
      }))

      const response = await fetch(`${API_URL}/api/tickets/${ticketNumber}/execute`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        throw new Error('Failed to start execution')
      }
      
      await response.json()
      
      setTickets(prev => prev.map(t =>
        t.number === ticketNumber 
          ? { ...t, status: 'in_progress' }
          : t
      ))
      
      startPolling(ticketNumber)
    } catch (err) {
      setJobData(prev => ({
        ...prev,
        [ticketNumber]: { 
          job: null, 
          isPolling: false, 
          error: err instanceof Error ? err.message : 'Execution failed' 
        }
      }))
    }
  }

  const handleCancel = async (ticketNumber: number) => {
    try {
      if (pollingIntervals.current[ticketNumber]) {
        clearInterval(pollingIntervals.current[ticketNumber])
        delete pollingIntervals.current[ticketNumber]
      }

      const response = await fetch(`${API_URL}/api/tickets/${ticketNumber}/cancel`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        throw new Error('Failed to cancel job')
      }
      
      setJobData(prev => ({
        ...prev,
        [ticketNumber]: { 
          job: prev[ticketNumber]?.job ? { ...prev[ticketNumber].job!, status: 'failed', error_message: 'Cancelled by user' } : null,
          isPolling: false, 
          error: null 
        }
      }))
      
      setTickets(prev => prev.map(t => 
        t.number === ticketNumber 
          ? { ...t, status: 'scoped' }
          : t
      ))
    } catch (err) {
      console.error('Cancel failed:', err)
    }
  }

  const handleComplete = async (ticketNumber: number) => {
    try {
      const response = await fetch(`${API_URL}/api/tickets/${ticketNumber}/complete`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        throw new Error('Failed to mark ticket complete')
      }
      
      setTickets(prev => prev.map(t => 
        t.number === ticketNumber 
          ? { ...t, status: 'complete' }
          : t
      ))
    } catch (err) {
      console.error('Complete failed:', err)
    }
  }

  const handleScope = async (ticketNumber: number) => {
    const currentScope = scopeData[ticketNumber]
    
    if (currentScope?.expanded) {
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { ...prev[ticketNumber], expanded: false }
      }))
      return
    }

    if (currentScope?.analysis) {
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { ...prev[ticketNumber], expanded: true }
      }))
      return
    }

    setScopeData(prev => ({
      ...prev,
      [ticketNumber]: { loading: true, analysis: null, expanded: true }
    }))

    try {
      const response = await fetch(`${API_URL}/api/tickets/${ticketNumber}/scope`)
      if (!response.ok) {
        throw new Error('Failed to scope ticket')
      }
      const data = await response.json()
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { 
          loading: false, 
          analysis: data.analysis, 
          expanded: true 
        }
      }))
      
      setTickets(prev => prev.map(t => 
        t.number === ticketNumber 
          ? { ...t, status: 'scoped', analysis: data.analysis }
          : t
      ))
    } catch (err) {
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { loading: false, analysis: null, expanded: false }
      }))
    }
  }

  const newTickets = tickets.filter(t => t.status === 'new' || t.status === 'todo')
  const scopedTickets = tickets.filter(t => t.status === 'scoped' || t.status === 'in_progress')
  const reviewTickets = tickets.filter(t => t.status === 'review')
  const completeTickets = tickets.filter(t => t.status === 'complete' || t.status === 'done')

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-zinc-400">Loading tickets...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-red-400">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <div className="p-4">
        <div className="flex items-center gap-4 mb-6">
            <div className="flex items-center gap-2 bg-zinc-800/50 px-3 py-1.5 rounded-md">
              <span className="text-sm text-zinc-300">Issue Dashboard</span>
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            </div>
          <button className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-300">
            <Plus className="w-4 h-4" />
            New view
          </button>
        </div>

        <div className="flex items-center gap-2 mb-6 text-zinc-500">
          <Filter className="w-4 h-4" />
          <span className="text-sm">Filter by keyword or by field</span>
        </div>

        <div className="flex gap-6 overflow-x-auto pb-4">
          <Column 
            title="New" 
            count={newTickets.length} 
            tickets={newTickets}
            scopeData={scopeData}
            onScope={handleScope}
            columnType="new"
            jobData={jobData}
            onExecute={handleExecute}
            onCancel={handleCancel}
            onComplete={handleComplete}
          />
          <Column 
            title="Scoped" 
            count={scopedTickets.length} 
            tickets={scopedTickets}
            scopeData={scopeData}
            onScope={handleScope}
            columnType="scoped"
            jobData={jobData}
            onExecute={handleExecute}
            onCancel={handleCancel}
            onComplete={handleComplete}
          />
          <Column 
            title="Review" 
            count={reviewTickets.length} 
            tickets={reviewTickets}
            scopeData={scopeData}
            onScope={handleScope}
            columnType="review"
            jobData={jobData}
            onExecute={handleExecute}
            onCancel={handleCancel}
            onComplete={handleComplete}
          />
          <Column 
            title="Complete" 
            count={completeTickets.length} 
            tickets={completeTickets}
            scopeData={scopeData}
            onScope={handleScope}
            columnType="complete"
            jobData={jobData}
            onExecute={handleExecute}
            onCancel={handleCancel}
            onComplete={handleComplete}
          />
          <div className="flex items-start">
            <button className="p-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 rounded-md">
              <Plus className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
