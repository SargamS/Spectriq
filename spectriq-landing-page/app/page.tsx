'use client'

import { Mail, Lock, Cloud, Radio, Users, Shield, ArrowRight, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { setUserEmail, isSignedIn } from '@/lib/api'

export default function LandingPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // If we already "know" this browser, skip straight to the dashboard.
  useEffect(() => {
    if (isSignedIn()) {
      router.replace('/dashboard')
    }
  }, [router])

  const handleContinue = () => {
    setError('')

    if (!email.trim()) {
      setError('Enter an email to continue.')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter a valid email address.')
      return
    }

    setSubmitting(true)
    // The backend doesn't implement real authentication yet (see
    // app/auth.py) - it identifies a user purely by the X-User-Email
    // header, creating the account on first sight. So there's nothing to
    // "check" here; we just remember the email for future requests.
    setUserEmail(email.trim())
    router.push('/dashboard')
  }

  const features = [
    { icon: Radio, label: 'Fast Transcription', description: 'Lightning-quick audio processing' },
    { icon: Radio, label: 'AI Summaries', description: 'Intelligent meeting distillation' },
    { icon: Users, label: 'Speaker Detection', description: 'Know who said what' },
    { icon: Shield, label: 'Private & Secure', description: 'Your data stays safe' },
  ]

  return (
    <div className="min-h-screen bg-[#0A0A0B] relative overflow-hidden">
      {/* Subtle dot grid background */}
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: 'radial-gradient(circle, #F5F5F0 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <div className="relative z-10 flex h-screen">
        {/* LEFT SIDE */}
        <div className="hidden lg:flex flex-1 flex-col justify-between p-12">
          {/* Header */}
          <div>
            <div className="flex items-center gap-3 mb-12">
              <div className="w-10 h-10 bg-[#E8527A] rounded-lg flex items-center justify-center">
                <Radio className="w-6 h-6 text-white" strokeWidth={1.5} />
              </div>
              <span className="text-2xl font-bold text-[#F5F5F0]">Spectriq</span>
            </div>

            {/* Eyebrow label */}
            <div className="text-[#E8527A] text-xs font-bold tracking-widest mb-4">
              WELCOME
            </div>

            {/* Main headline */}
            <h1 className="text-6xl leading-tight font-bold text-[#F5F5F0] mb-6 tracking-tight">
              Meetings,<br />
              distilled.
            </h1>

            {/* Subtext */}
            <p className="text-lg text-[#F5E6D3] leading-relaxed max-w-xl">
              Spectriq turns raw recordings into clear summaries, action items, and
              decisions — automatically.
            </p>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-2 gap-6 max-w-xl">
            {features.map((feature, idx) => {
              const Icon = feature.icon
              return (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-[#141416] border border-[#2A2A2E] hover:border-[#E8527A] transition-colors"
                >
                  <Icon className="w-5 h-5 text-[#E8527A] mb-3" strokeWidth={1.5} />
                  <h3 className="text-sm font-bold text-[#F5F5F0] mb-1">{feature.label}</h3>
                  <p className="text-xs text-[#8A8A8E]">{feature.description}</p>
                </div>
              )
            })}
          </div>
        </div>

        {/* RIGHT SIDE - Sign In Card */}
        <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
          <div className="w-full max-w-sm">
            <div className="rounded-2xl bg-[#141416] border border-[#2A2A2E] p-8 md:p-10">
              {/* Logo */}
              <div className="flex justify-center mb-8">
                <div className="w-12 h-12 bg-[#E8527A] rounded-lg flex items-center justify-center">
                  <Radio className="w-7 h-7 text-white" strokeWidth={1.5} />
                </div>
              </div>

              {/* Title */}
              <h2 className="text-center text-2xl font-bold text-[#F5F5F0] mb-2">Spectriq</h2>
              <p className="text-center text-[#8A8A8E] text-sm mb-8">
                Sign in to start summarizing your meetings.
              </p>

              {/* Form */}
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-[#F5F5F0] mb-2">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleContinue()}
                    placeholder="you@example.com"
                    className="w-full px-4 py-3 rounded-lg bg-[#0A0A0B] border border-[#2A2A2E] text-[#F5F5F0] placeholder-[#8A8A8E] focus:outline-none focus:border-[#E8527A] focus:ring-1 focus:ring-[#E8527A] transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-[#F5F5F0] mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleContinue()}
                    placeholder="••••••••"
                    className="w-full px-4 py-3 rounded-lg bg-[#0A0A0B] border border-[#2A2A2E] text-[#F5F5F0] placeholder-[#8A8A8E] focus:outline-none focus:border-[#E8527A] focus:ring-1 focus:ring-[#E8527A] transition-colors"
                  />
                </div>

                {error && <p className="text-sm text-[#E8527A]">{error}</p>}
              </div>

              {/* CTA Button */}
              <button
                onClick={handleContinue}
                disabled={submitting}
                className="w-full py-3 rounded-lg bg-[#E8527A] text-white font-semibold flex items-center justify-center gap-2 hover:bg-[#d63f6f] transition-colors disabled:opacity-70"
              >
                {submitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    Continue <ArrowRight className="w-4 h-4" strokeWidth={2} />
                  </>
                )}
              </button>

              {/* Footer security note */}
              <div className="mt-6 pt-6 border-t border-[#2A2A2E]">
                <div className="flex items-center justify-center gap-2 text-xs text-[#8A8A8E]">
                  <Shield className="w-4 h-4 text-[#E8527A]" strokeWidth={1.5} />
                  <span>Your recordings are processed securely and never shared.</span>
                </div>
              </div>
            </div>

            {/* Mobile-only header on small screens */}
            <div className="lg:hidden text-center mt-8">
              <div className="flex items-center justify-center gap-3 mb-4">
                <div className="w-10 h-10 bg-[#E8527A] rounded-lg flex items-center justify-center">
                  <Radio className="w-6 h-6 text-white" strokeWidth={1.5} />
                </div>
                <span className="text-2xl font-bold text-[#F5F5F0]">Spectriq</span>
              </div>
              <p className="text-[#8A8A8E] text-sm">Transform meetings into actionable insights</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
