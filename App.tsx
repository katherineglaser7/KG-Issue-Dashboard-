import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Circle, Plus, MoreHorizontal, Filter } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ConfidenceBreakdown {
  requirement_clarity: number
  code_complexity: number
  test_coverage: number
  risk_assessment: number
}

interface ConfidenceScore {
  total: number
  breakdown: ConfidenceBreakdown
}

interface Ticket {
  id: number
  number: number
  title: string
  body: string | null
  status: string
  labels: string[]
  created_at: string
  updated_at: string
  html_url: string
  confidence_score: ConfidenceScore | null
}

interface ScopeData {
  [key: number]: {
    loading: boolean
    score: ConfidenceScore | null
    expanded: boolean
  }
}

function TicketCard({ 
  ticket, 
  scopeData, 
  onScope 
}: { 
  ticket: Ticket
  scopeData: ScopeData
  onScope: (ticketNumber: number) => void
}) {
  const scope = scopeData[ticket.number]
  const isExpanded = scope?.expanded || false
  const isLoading = scope?.loading || false
  const score = scope?.score || null

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400'
    if (score >= 60) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getMetricLabel = (key: string) => {
    const labels: Record<string, string> = {
      requirement_clarity: 'Requirement Clarity',
      code_complexity: 'Code Complexity',
      test_coverage: 'Test Coverage',
      risk_assessment: 'Risk Assessment',
    }
    return labels[key] || key
  }

  return (
    <Card className="bg-zinc-800/50 border-zinc-700 p-3 mb-2 hover:border-zinc-500 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Circle className="w-4 h-4 text-zinc-500" strokeDasharray="4 2" />
          <span className="text-xs text-zinc-500">Draft</span>
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
      
      {ticket.status === 'todo' && (
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
            ) : score ? (
              <div className="bg-zinc-900/50 rounded-md p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-400">Confidence Score</span>
                  <span className={`text-lg font-bold ${getScoreColor(score.total)}`}>
                    {score.total}/100
                  </span>
                </div>
                <div className="space-y-2">
                  {Object.entries(score.breakdown).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-xs text-zinc-500">{getMetricLabel(key)}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${
                              value >= 20 ? 'bg-green-500' : 
                              value >= 15 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${(value / 25) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-zinc-400 w-8 text-right">{value}/25</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </CollapsibleContent>
        </Collapsible>
      )}
    </Card>
  )
}

function Column({ 
  title, 
  count, 
  tickets, 
  scopeData, 
  onScope 
}: { 
  title: string
  count: number
  tickets: Ticket[]
  scopeData: ScopeData
  onScope: (ticketNumber: number) => void
}) {
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

  useEffect(() => {
    fetchTickets()
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

  const handleScope = async (ticketNumber: number) => {
    const currentScope = scopeData[ticketNumber]
    
    if (currentScope?.expanded) {
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { ...prev[ticketNumber], expanded: false }
      }))
      return
    }

    if (currentScope?.score) {
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { ...prev[ticketNumber], expanded: true }
      }))
      return
    }

    setScopeData(prev => ({
      ...prev,
      [ticketNumber]: { loading: true, score: null, expanded: true }
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
          score: data.confidence_score, 
          expanded: true 
        }
      }))
    } catch (err) {
      setScopeData(prev => ({
        ...prev,
        [ticketNumber]: { loading: false, score: null, expanded: false }
      }))
    }
  }

  const todoTickets = tickets.filter(t => t.status === 'todo')
  const inProgressTickets = tickets.filter(t => t.status === 'in_progress')
  const doneTickets = tickets.filter(t => t.status === 'done')

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
            <span className="text-sm text-zinc-300">View 1</span>
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
            title="Todo" 
            count={todoTickets.length} 
            tickets={todoTickets}
            scopeData={scopeData}
            onScope={handleScope}
          />
          <Column 
            title="In Progress" 
            count={inProgressTickets.length} 
            tickets={inProgressTickets}
            scopeData={scopeData}
            onScope={handleScope}
          />
          <Column 
            title="Done" 
            count={doneTickets.length} 
            tickets={doneTickets}
            scopeData={scopeData}
            onScope={handleScope}
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
