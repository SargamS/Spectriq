'use client'

import { LogOut, Upload, Cloud, Radio, Loader2, AlertCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth, useClerk, useUser } from '@clerk/nextjs'
import {
  setTokenProvider,
  listMeetings,
  uploadMeeting,
  ApiError,
  type MeetingSummary,
} from '@/lib/api'

const STATUS_LABELS: Record<string, string> = {
  queued: 'Queued',
  extracting: 'Extracting audio',
  transcribing: 'Transcribing',
  summarizing: 'Summarizing',
  indexing: 'Finishing up',
  done: 'Ready',
  failed: 'Failed',
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return (
    d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' at ' +
    d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  )
}

export default function Dashboard() {
  const router = useRouter()
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const { user } = useUser()
  const { signOut } = useClerk()
  const [isDragActive, setIsDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState('')

  const [meetings, setMeetings] = useState<MeetingSummary[]>([])
  const [loadingMeetings, setLoadingMeetings] = useState(true)
  const [meetingsError, setMeetingsError] = useState('')
  const email = user?.primaryEmailAddress?.emailAddress || ''

  // Middleware already blocks unauthenticated visits to /dashboard, but
  // this covers the client-side moment before that's fully resolved.
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.replace('/')
    }
  }, [isLoaded, isSignedIn, router])

  useEffect(() => {
    setTokenProvider(getToken)
  }, [getToken])

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      refreshMeetings()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn])

  const refreshMeetings = async () => {
    setLoadingMeetings(true)
    setMeetingsError('')
    try {
      const data = await listMeetings()
      setMeetings(data)
    } catch (err) {
      setMeetingsError(
        err instanceof ApiError
          ? err.message
          : 'Could not reach the Spectriq backend. Is it running?'
      )
    } finally {
      setLoadingMeetings(false)
    }
  }

  const quickStartOptions = ['Team Standup', 'Client Call', 'Lecture Recording', 'Interview']

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragActive(true)
    } else if (e.type === 'dragleave') {
      setIsDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0])
      setUploadError('')
    }
  }

  const handleFileClick = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'audio/*,video/*'
    input.onchange = (e: any) => {
      if (e.target.files?.[0]) {
        setSelectedFile(e.target.files[0])
        setUploadError('')
      }
    }
    input.click()
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    setUploading(true)
    setUploadProgress(0)
    setUploadError('')
    try {
      const { meeting_id } = await uploadMeeting(selectedFile, setUploadProgress)
      router.push(`/results?id=${meeting_id}`)
    } catch (err) {
      setUploading(false)
      setUploadError(
        err instanceof ApiError ? err.message : 'Upload failed. Is the Spectriq backend running?'
      )
    }
  }

  const handleSignOut = () => {
    signOut(() => router.push('/'))
  }

  const initials = (email || 'ME').split(/[@.]/)[0].slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-[#F5F5F0]">
      {/* Top Navigation */}
      <nav className="border-b border-[#2A2A2E] px-6 md:px-12 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-[#E8527A] rounded-lg flex items-center justify-center">
            <Radio className="w-5 h-5 text-white" strokeWidth={1.5} />
          </div>
          <span className="text-xl font-bold">Spectriq</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-full bg-[#E8527A] flex items-center justify-center text-sm font-semibold">
            {initials || 'U'}
          </div>
          <span className="text-sm text-[#8A8A8E] hidden sm:inline">{email}</span>
          <button
            onClick={handleSignOut}
            className="px-4 py-2 rounded-lg border border-[#2A2A2E] text-[#F5F5F0] hover:border-[#E8527A] transition-colors flex items-center gap-2 text-sm"
          >
            <LogOut className="w-4 h-4" strokeWidth={1.5} />
            Sign Out
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-5xl mx-auto px-6 md:px-12 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl md:text-6xl font-bold mb-4 tracking-tight">
            Upload. Transcribe. Understand.
          </h1>
          <p className="text-lg text-[#F5E6D3] max-w-2xl mx-auto leading-relaxed">
            Drop in a meeting recording — audio or video — and get a structured summary in
            minutes.
          </p>
        </div>

        {/* Upload Zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={!uploading ? handleFileClick : undefined}
          className={`relative rounded-2xl border-2 border-dashed transition-all p-16 text-center mb-4 ${
            uploading ? 'cursor-default' : 'cursor-pointer'
          } ${
            isDragActive
              ? 'border-[#E8527A] bg-[#E8527A]/5'
              : 'border-[#2A2A2E] hover:border-[#E8527A] hover:bg-[#E8527A]/5'
          }`}
        >
          <Cloud className="w-12 h-12 text-[#E8527A] mx-auto mb-4" strokeWidth={1.5} />

          <h2 className="text-xl font-semibold mb-2">Drag & drop your file here</h2>
          <p className="text-[#8A8A8E] mb-6">or click to browse</p>

          {selectedFile && (
            <p className="text-sm text-[#F5E6D3] mb-4">
              <span className="font-semibold">Selected:</span> {selectedFile.name}
            </p>
          )}

          <p className="text-xs text-[#8A8A8E]">
            Supports MP3, WAV, M4A, MP4, MOV — up to 500MB
          </p>
        </div>

        {uploadError && (
          <div className="max-w-md mx-auto mb-8 rounded-lg border border-[#E8527A]/40 bg-[#E8527A]/10 px-4 py-3 flex items-start gap-2 text-sm text-[#F5E6D3]">
            <AlertCircle className="w-4 h-4 text-[#E8527A] flex-shrink-0 mt-0.5" strokeWidth={1.5} />
            <span>{uploadError}</span>
          </div>
        )}

        {/* Upload Button */}
        <div className="flex flex-col items-center gap-3 mb-16">
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className={`px-8 py-3 rounded-lg font-semibold flex items-center gap-2 transition-all ${
              selectedFile && !uploading
                ? 'bg-[#E8527A] text-white hover:bg-[#d63f6f]'
                : 'bg-[#2A2A2E] text-[#8A8A8E] cursor-not-allowed'
            }`}
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading{uploadProgress > 0 ? ` ${uploadProgress}%` : '…'}
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" strokeWidth={1.5} />
                Upload & Summarize
              </>
            )}
          </button>
        </div>

        {/* Quick-Start Chips (decorative labels - no backend equivalent yet) */}
        <div className="flex flex-wrap justify-center gap-3 mb-16">
          {quickStartOptions.map((option) => (
            <span
              key={option}
              className="px-4 py-2 rounded-full border border-[#2A2A2E] text-sm text-[#8A8A8E]"
            >
              {option}
            </span>
          ))}
        </div>

        {/* Recent Meetings Section */}
        <div>
          <h3 className="text-2xl font-bold mb-8">Recent Meetings</h3>

          {loadingMeetings ? (
            <div className="rounded-2xl bg-[#141416] border border-[#2A2A2E] p-12 text-center">
              <Loader2 className="w-8 h-8 text-[#E8527A] mx-auto mb-4 animate-spin" />
              <p className="text-[#8A8A8E]">Loading your meetings…</p>
            </div>
          ) : meetingsError ? (
            <div className="rounded-2xl bg-[#141416] border border-[#2A2A2E] p-12 text-center">
              <AlertCircle className="w-10 h-10 text-[#E8527A] mx-auto mb-4" strokeWidth={1.5} />
              <h4 className="text-lg font-semibold text-[#F5F5F0] mb-2">
                Couldn&apos;t load meetings
              </h4>
              <p className="text-[#8A8A8E] mb-4">{meetingsError}</p>
              <button
                onClick={refreshMeetings}
                className="px-4 py-2 rounded-lg border border-[#E8527A] text-[#E8527A] hover:bg-[#E8527A]/10 transition-colors text-sm"
              >
                Try again
              </button>
            </div>
          ) : meetings.length === 0 ? (
            <div className="rounded-2xl bg-[#141416] border border-[#2A2A2E] p-12 text-center">
              <Radio className="w-12 h-12 text-[#8A8A8E] mx-auto mb-4 opacity-50" strokeWidth={1.5} />
              <h4 className="text-lg font-semibold text-[#F5F5F0] mb-2">No meetings yet.</h4>
              <p className="text-[#8A8A8E]">Upload your first recording to get started.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {meetings.map((m) => (
                <Link key={m.id} href={`/results?id=${m.id}`}>
                  <div className="flex items-center justify-between gap-4 rounded-xl bg-[#141416] border border-[#2A2A2E] hover:border-[#E8527A] transition-colors p-5 cursor-pointer">
                    <div className="min-w-0">
                      <h4 className="font-semibold text-[#F5F5F0] truncate">
                        {m.title || 'Untitled meeting'}
                      </h4>
                      <p className="text-sm text-[#8A8A8E]">{formatDate(m.created_at)}</p>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold flex-shrink-0 ${
                        m.status === 'done'
                          ? 'bg-[#2ECC71]/10 text-[#2ECC71]'
                          : m.status === 'failed'
                          ? 'bg-[#E8527A]/10 text-[#E8527A]'
                          : 'bg-[#F5E6D3]/10 text-[#F5E6D3]'
                      }`}
                    >
                      {STATUS_LABELS[m.status] || m.status}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
