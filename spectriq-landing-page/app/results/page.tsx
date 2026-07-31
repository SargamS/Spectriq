'use client'

import {
  LogOut,
  Download,
  Copy,
  CheckCircle2,
  Circle,
  Radio,
  Search,
  Send,
  ChevronDown,
  AlertCircle,
  ArrowLeft,
} from 'lucide-react'
import { Suspense, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth, useClerk } from '@clerk/nextjs'
import {
  setTokenProvider,
  getMeeting,
  chatWithMeeting,
  ApiError,
  type MeetingDetail,
  type ChatMessage as ApiChatMessage,
  type ChatSource,
} from '@/lib/api'

type Tab = 'summary' | 'transcript' | 'action-items' | 'chat'

type Message = {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
  sources?: ChatSource[]
}

const PROCESSING_STEPS: { key: string; label: string }[] = [
  { key: 'extracting', label: 'Extracting Audio' },
  { key: 'transcribing', label: 'Transcribing' },
  { key: 'summarizing', label: 'Summarizing' },
  { key: 'indexing', label: 'Finishing Up' },
]

const STATUS_ORDER = ['queued', 'extracting', 'transcribing', 'summarizing', 'indexing', 'done']

function currentStepIndex(status: string): number {
  // Map backend status -> index into PROCESSING_STEPS, clamped so
  // "queued" shows step 0 in progress and "done"/"indexing" show all
  // steps complete.
  const idx = STATUS_ORDER.indexOf(status)
  if (idx <= 0) return 0
  return Math.min(idx - 1, PROCESSING_STEPS.length - 1)
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function ResultsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const meetingId = searchParams.get('id')

  const [activeTab, setActiveTab] = useState<Tab>('summary')
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null)
  const [loadError, setLoadError] = useState('')
  const [notFound, setNotFound] = useState(false)

  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoadingResponse, setIsLoadingResponse] = useState(false)
  const [chatError, setChatError] = useState('')
  const [expandedSource, setExpandedSource] = useState<string | null>(null)
  const [transcriptSearch, setTranscriptSearch] = useState('')
  const [copiedActionItems, setCopiedActionItems] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ---------- auth guard ----------
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const { signOut } = useClerk()

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.replace('/')
    }
  }, [isLoaded, isSignedIn, router])

  useEffect(() => {
    setTokenProvider(getToken)
  }, [getToken])

  // ---------- poll meeting status until it finishes processing ----------
  useEffect(() => {
    if (!meetingId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const poll = async () => {
      try {
        const data = await getMeeting(meetingId)
        if (cancelled) return
        setMeeting(data)
        setLoadError('')
        if (data.status !== 'done' && data.status !== 'failed') {
          timer = setTimeout(poll, 2000)
        }
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true)
        } else {
          setLoadError(
            err instanceof ApiError
              ? err.message
              : 'Could not reach the Spectriq backend. Is it running?'
          )
          timer = setTimeout(poll, 3000)
        }
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [meetingId])

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !meeting) return
    setChatError('')

    const text = inputValue.trim()
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    setInputValue('')
    setIsLoadingResponse(true)

    const history: ApiChatMessage[] = messages.map((m) => ({
      role: m.type === 'user' ? 'user' : 'assistant',
      content: m.content,
    }))

    try {
      const res = await chatWithMeeting(meeting.id, text, history)
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: res.response,
        timestamp: new Date(),
        sources: res.sources,
      }
      setMessages((prev) => [...prev, aiMessage])
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : 'Failed to reach the chat endpoint.')
    } finally {
      setIsLoadingResponse(false)
    }
  }

  const handleCopyActionItems = async () => {
    if (!meeting?.action_items?.length) return
    const text = meeting.action_items
      .map((a) => `- ${a.text}${a.assignee ? ` (${a.assignee})` : ''}`)
      .join('\n')
    await navigator.clipboard.writeText(text)
    setCopiedActionItems(true)
    setTimeout(() => setCopiedActionItems(false), 2000)
  }

  const handleDownload = () => {
    if (!meeting) return
    const lines = [
      `# ${meeting.title || 'Untitled meeting'}`,
      '',
      '## Summary',
      meeting.summary || '(none)',
      '',
      '## Key Decisions',
      ...(meeting.key_decisions?.length
        ? meeting.key_decisions.map((d) => `- ${d}`)
        : ['(none)']),
      '',
      '## Action Items',
      ...(meeting.action_items?.length
        ? meeting.action_items.map((a) => `- ${a.text}${a.assignee ? ` (${a.assignee})` : ''}`)
        : ['(none)']),
      '',
      '## Open Questions',
      ...(meeting.open_questions?.length ? meeting.open_questions.map((q) => `- ${q}`) : ['(none)']),
      '',
      '## Transcript',
      meeting.transcript_text || '(none)',
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(meeting.title || 'meeting').replace(/[^\w\-]+/g, '_')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleSignOut = () => {
    signOut(() => router.push('/'))
  }

  const suggestedQuestions = [
    'What were the main decisions?',
    'What did the team say about the budget?',
    'Summarize the action items',
    'What are the open questions?',
  ]

  const filteredTranscript = (meeting?.transcript_segments || []).filter((seg) =>
    seg.text.toLowerCase().includes(transcriptSearch.toLowerCase())
  )

  const isProcessing = meeting ? meeting.status !== 'done' && meeting.status !== 'failed' : true

  // ---------- guard states ----------
  if (!meetingId) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] text-[#F5F5F0] flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-10 h-10 text-[#E8527A] mx-auto mb-4" strokeWidth={1.5} />
          <h2 className="text-lg font-semibold mb-2">No meeting selected</h2>
          <p className="text-[#8A8A8E] mb-6">
            Open a meeting from your dashboard to see its results here.
          </p>
          <Link href="/dashboard">
            <button className="px-4 py-2 rounded-lg bg-[#E8527A] text-white font-semibold inline-flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" /> Back to dashboard
            </button>
          </Link>
        </div>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] text-[#F5F5F0] flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-10 h-10 text-[#E8527A] mx-auto mb-4" strokeWidth={1.5} />
          <h2 className="text-lg font-semibold mb-2">Meeting not found</h2>
          <p className="text-[#8A8A8E] mb-6">
            This meeting doesn&apos;t exist, or doesn&apos;t belong to your account.
          </p>
          <Link href="/dashboard">
            <button className="px-4 py-2 rounded-lg bg-[#E8527A] text-white font-semibold inline-flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" /> Back to dashboard
            </button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-[#F5F5F0]">
      {/* Top Navigation */}
      <nav className="border-b border-[#2A2A2E] px-6 md:px-12 py-4 flex items-center justify-between sticky top-0 z-40 bg-[#0A0A0B]">
        <Link href="/dashboard">
          <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
            <div className="w-9 h-9 bg-[#E8527A] rounded-lg flex items-center justify-center">
              <Radio className="w-5 h-5 text-white" strokeWidth={1.5} />
            </div>
            <span className="text-xl font-bold">Spectriq</span>
          </div>
        </Link>

        <button
          onClick={handleSignOut}
          className="px-4 py-2 rounded-lg border border-[#2A2A2E] text-[#F5F5F0] hover:border-[#E8527A] transition-colors flex items-center gap-2 text-sm"
        >
          <LogOut className="w-4 h-4" strokeWidth={1.5} />
          Sign Out
        </button>
      </nav>

      {/* Processing State */}
      {isProcessing && (
        <div className="fixed inset-0 bg-[#0A0A0B]/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#141416] border border-[#2A2A2E] rounded-2xl p-12 max-w-md w-full mx-4 text-center">
            {loadError && (
              <p className="text-xs text-[#E8527A] mb-4">{loadError} — retrying…</p>
            )}
            <div className="mb-8">
              <div className="w-16 h-16 mx-auto mb-6 relative">
                <div className="absolute inset-0 rounded-full border-4 border-[#2A2A2E]" />
                <div
                  className="absolute inset-0 rounded-full border-4 border-transparent border-t-[#E8527A] animate-spin"
                  style={{ animation: 'spin 2s linear infinite' }}
                />
              </div>
            </div>

            {/* Progress Steps */}
            <div className="flex items-center justify-between mb-8 px-4">
              {PROCESSING_STEPS.map((step, idx) => {
                const stepIdx = meeting ? currentStepIndex(meeting.status) : 0
                return (
                  <div key={step.key} className="flex flex-col items-center">
                    <div
                      className={`w-8 h-8 rounded-full border-2 flex items-center justify-center mb-2 transition-all ${
                        idx <= stepIdx ? 'bg-[#E8527A] border-[#E8527A]' : 'border-[#2A2A2E]'
                      }`}
                    >
                      {idx < stepIdx && <CheckCircle2 className="w-5 h-5 text-white" strokeWidth={2} />}
                      {idx === stepIdx && (
                        <div className="w-2 h-2 bg-[#F5E6D3] rounded-full animate-pulse" />
                      )}
                      {idx > stepIdx && <Circle className="w-5 h-5 text-[#8A8A8E]" strokeWidth={1} />}
                    </div>
                    <span className="text-xs text-[#8A8A8E] text-center">{step.label}</span>
                  </div>
                )
              })}
            </div>

            <p className="text-[#F5E6D3] text-sm">
              {PROCESSING_STEPS[meeting ? currentStepIndex(meeting.status) : 0].label}…
            </p>
          </div>
        </div>
      )}

      {/* Failed State */}
      {meeting?.status === 'failed' && (
        <div className="max-w-2xl mx-auto px-6 md:px-12 py-16 text-center">
          <AlertCircle className="w-12 h-12 text-[#E8527A] mx-auto mb-4" strokeWidth={1.5} />
          <h1 className="text-2xl font-bold mb-2">Processing failed</h1>
          <p className="text-[#8A8A8E] mb-8">
            {meeting.error_message || 'Something went wrong while processing this meeting.'}
          </p>
          <Link href="/dashboard">
            <button className="px-4 py-2 rounded-lg bg-[#E8527A] text-white font-semibold inline-flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" /> Back to dashboard
            </button>
          </Link>
        </div>
      )}

      {/* Main Content */}
      {meeting && meeting.status === 'done' && (
        <div className="max-w-6xl mx-auto px-6 md:px-12 py-8">
          {/* Header */}
          <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold mb-2">{meeting.title || 'Untitled meeting'}</h1>
              <div className="flex flex-wrap gap-4 text-sm text-[#8A8A8E]">
                <span>{new Date(meeting.created_at).toLocaleString()}</span>
                {meeting.duration_seconds != null && (
                  <>
                    <span>•</span>
                    <span>{Math.round(meeting.duration_seconds / 60)} min</span>
                  </>
                )}
              </div>
            </div>
            <button
              onClick={handleDownload}
              className="px-4 py-2 rounded-lg border border-[#E8527A] text-[#E8527A] hover:bg-[#E8527A]/10 transition-colors flex items-center gap-2 w-fit"
            >
              <Download className="w-4 h-4" strokeWidth={1.5} />
              Download
            </button>
          </div>

          {/* Tab Bar */}
          <div className="flex gap-8 border-b border-[#2A2A2E] mb-8 overflow-x-auto">
            {(['summary', 'transcript', 'action-items', 'chat'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`pb-4 px-2 font-semibold text-sm capitalize whitespace-nowrap transition-colors relative ${
                  activeTab === tab ? 'text-[#E8527A]' : 'text-[#8A8A8E] hover:text-[#F5F5F0]'
                }`}
              >
                {tab === 'action-items' ? 'Action Items' : tab}
                {activeTab === tab && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#E8527A]" />
                )}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="pb-8">
            {/* SUMMARY TAB */}
            {activeTab === 'summary' && (
              <div className="space-y-6">
                <div className="rounded-xl bg-[#141416] border border-[#2A2A2E] p-6">
                  <h2 className="text-lg font-bold mb-4 text-[#F5E6D3]">Overview</h2>
                  <p className="text-[#F5F5F0] leading-relaxed">
                    {meeting.summary || 'No summary available.'}
                  </p>
                </div>

                <div className="rounded-xl bg-[#141416] border border-[#2A2A2E] p-6">
                  <h2 className="text-lg font-bold mb-4 text-[#F5E6D3]">Key Decisions</h2>
                  {meeting.key_decisions?.length ? (
                    <ul className="space-y-3">
                      {meeting.key_decisions.map((decision, idx) => (
                        <li key={idx} className="flex gap-3 text-[#F5F5F0]">
                          <span className="w-2 h-2 rounded-full bg-[#E8527A] mt-2 flex-shrink-0" />
                          {decision}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[#8A8A8E] text-sm">No decisions recorded.</p>
                  )}
                </div>

                <div className="rounded-xl bg-[#141416] border border-[#2A2A2E] p-6">
                  <h2 className="text-lg font-bold mb-4 text-[#F5E6D3]">Open Questions</h2>
                  {meeting.open_questions?.length ? (
                    <ul className="space-y-3">
                      {meeting.open_questions.map((question, idx) => (
                        <li key={idx} className="flex gap-3 text-[#F5F5F0]">
                          <span className="w-2 h-2 rounded-full bg-[#F5E6D3] mt-2 flex-shrink-0" />
                          {question}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[#8A8A8E] text-sm">No open questions.</p>
                  )}
                </div>
              </div>
            )}

            {/* TRANSCRIPT TAB */}
            {activeTab === 'transcript' && (
              <div>
                <div className="mb-6 relative">
                  <Search className="absolute left-4 top-3.5 w-4 h-4 text-[#8A8A8E]" strokeWidth={1.5} />
                  <input
                    type="text"
                    placeholder="Search transcript..."
                    value={transcriptSearch}
                    onChange={(e) => setTranscriptSearch(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-[#141416] border border-[#2A2A2E] rounded-lg text-[#F5F5F0] placeholder-[#8A8A8E] focus:outline-none focus:border-[#E8527A] focus:ring-1 focus:ring-[#E8527A]"
                  />
                </div>

                {filteredTranscript.length ? (
                  <div className="space-y-4">
                    {filteredTranscript.map((item, idx) => (
                      <div key={idx} className="flex gap-4 pb-4 border-b border-[#2A2A2E] last:border-0">
                        <span className="text-[#8A8A8E] text-sm font-mono flex-shrink-0 min-w-12">
                          {formatTimestamp(item.start)}
                        </span>
                        <p className="text-[#F5F5F0] text-sm leading-relaxed flex-1">{item.text}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[#8A8A8E] text-sm">
                    {transcriptSearch ? 'No matching transcript lines.' : 'No transcript available.'}
                  </p>
                )}
              </div>
            )}

            {/* ACTION ITEMS TAB */}
            {activeTab === 'action-items' && (
              <div>
                {!!meeting.action_items?.length && (
                  <div className="mb-6 flex justify-end">
                    <button
                      onClick={handleCopyActionItems}
                      className="px-4 py-2 rounded-lg border border-[#E8527A] text-[#E8527A] hover:bg-[#E8527A]/10 transition-colors flex items-center gap-2 text-sm"
                    >
                      <Copy className="w-4 h-4" strokeWidth={1.5} />
                      {copiedActionItems ? 'Copied!' : 'Copy all'}
                    </button>
                  </div>
                )}

                {meeting.action_items?.length ? (
                  <div className="space-y-3">
                    {meeting.action_items.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-4 p-4 rounded-lg bg-[#141416] border border-[#2A2A2E] hover:border-[#E8527A] transition-colors"
                      >
                        <div className="flex-1">
                          <p className="text-sm font-medium text-[#F5F5F0]">{item.text}</p>
                        </div>
                        {item.assignee && (
                          <span className="px-3 py-1 rounded-full bg-[#E8527A]/10 text-[#E8527A] text-xs font-semibold">
                            {item.assignee}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[#8A8A8E] text-sm">No action items identified.</p>
                )}
              </div>
            )}

            {/* CHAT TAB */}
            {activeTab === 'chat' && (
              <div className="flex flex-col h-[600px] rounded-xl bg-[#141416] border border-[#2A2A2E] overflow-hidden">
                {/* Chat Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center">
                      <p className="text-2xl font-semibold text-[#F5F5F0] mb-6">
                        Ask anything about this meeting.
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-md">
                        {suggestedQuestions.map((q, idx) => (
                          <button
                            key={idx}
                            onClick={() => setInputValue(q)}
                            className="px-4 py-3 rounded-lg border border-[#2A2A2E] text-[#F5E6D3] hover:border-[#E8527A] hover:text-[#E8527A] transition-colors text-sm font-medium"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <>
                      {messages.map((msg) => (
                        <div
                          key={msg.id}
                          className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
                              msg.type === 'user'
                                ? 'bg-[#E8527A] text-white'
                                : 'bg-[#0A0A0B] border border-[#2A2A2E] text-[#F5F5F0] flex gap-3'
                            }`}
                          >
                            {msg.type === 'ai' && (
                              <div className="w-6 h-6 rounded-full bg-[#E8527A] flex-shrink-0 flex items-center justify-center">
                                <Radio className="w-3.5 h-3.5 text-white" strokeWidth={2} />
                              </div>
                            )}
                            <div className="flex-1">
                              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                              {!!msg.sources?.length && (
                                <button
                                  onClick={() =>
                                    setExpandedSource(expandedSource === msg.id ? null : msg.id)
                                  }
                                  className="mt-2 text-xs flex items-center gap-1 opacity-70 hover:opacity-100 transition-opacity"
                                >
                                  <span>Sources ({msg.sources.length})</span>
                                  <ChevronDown
                                    className={`w-3 h-3 transition-transform ${
                                      expandedSource === msg.id ? 'rotate-180' : ''
                                    }`}
                                  />
                                </button>
                              )}
                              {expandedSource === msg.id && !!msg.sources?.length && (
                                <div className="mt-2 space-y-2">
                                  {msg.sources.map((s, i) => (
                                    <div
                                      key={i}
                                      className="p-2 bg-[#141416] rounded text-xs border border-[#2A2A2E]"
                                    >
                                      <span className="text-[#E8527A] font-mono">
                                        {formatTimestamp(s.start_timestamp)}
                                      </span>{' '}
                                      <span className="text-[#8A8A8E]">{s.chunk_text}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                      {isLoadingResponse && (
                        <div className="flex justify-start">
                          <div className="bg-[#0A0A0B] border border-[#2A2A2E] text-[#F5F5F0] px-4 py-3 rounded-lg flex gap-3">
                            <div className="w-6 h-6 rounded-full bg-[#E8527A] flex-shrink-0 flex items-center justify-center">
                              <Radio className="w-3.5 h-3.5 text-white" strokeWidth={2} />
                            </div>
                            <div className="flex gap-1">
                              <div className="w-2 h-2 bg-[#8A8A8E] rounded-full animate-bounce" />
                              <div
                                className="w-2 h-2 bg-[#8A8A8E] rounded-full animate-bounce"
                                style={{ animationDelay: '0.2s' }}
                              />
                              <div
                                className="w-2 h-2 bg-[#8A8A8E] rounded-full animate-bounce"
                                style={{ animationDelay: '0.4s' }}
                              />
                            </div>
                          </div>
                        </div>
                      )}
                      <div ref={messagesEndRef} />
                    </>
                  )}
                </div>

                {chatError && (
                  <div className="px-4 pb-2 text-xs text-[#E8527A]">{chatError}</div>
                )}

                {/* Chat Input */}
                <div className="border-t border-[#2A2A2E] p-4">
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                          e.preventDefault()
                          handleSendMessage()
                        }
                      }}
                      placeholder="Ask about this meeting..."
                      className="flex-1 px-4 py-3 rounded-lg bg-[#0A0A0B] border border-[#2A2A2E] text-[#F5F5F0] placeholder-[#8A8A8E] focus:outline-none focus:border-[#E8527A] focus:ring-1 focus:ring-[#E8527A]"
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={!inputValue.trim() || isLoadingResponse}
                      className={`px-4 py-3 rounded-lg flex items-center justify-center transition-colors ${
                        inputValue.trim() && !isLoadingResponse
                          ? 'bg-[#E8527A] text-white hover:bg-[#d63f6f]'
                          : 'bg-[#2A2A2E] text-[#8A8A8E] cursor-not-allowed'
                      }`}
                    >
                      <Send className="w-4 h-4" strokeWidth={2} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  )
}

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center text-[#8A8A8E]">
          Loading…
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  )
}
