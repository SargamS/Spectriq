'use client'

import { Radio, Shield, ArrowRight } from 'lucide-react'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'

// Marketing/landing page. Actual sign-in lives at /sign-in and is handled
// entirely by Clerk - this page just links there. (Previously this page
// embedded its own email + password form that never checked the password
// against anything, since the backend had no real auth - see app/auth.py
// on the backend for the real Clerk-based verification that replaced it.)
export default function LandingPage() {
  const router = useRouter()
  const { isSignedIn, isLoaded } = useAuth()

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      router.replace('/dashboard')
    }
  }, [isLoaded, isSignedIn, router])

  const features = [
    { icon: Radio, label: 'Fast Transcription', description: 'Lightning-quick audio processing' },
    { icon: Radio, label: 'AI Summaries', description: 'Intelligent meeting distillation' },
    { icon: Shield, label: 'Private & Secure', description: 'Your data stays safe' },
  ]

  return (
    <div className="min-h-screen bg-[#0A0A0B] relative overflow-hidden">
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: 'radial-gradient(circle, #F5F5F0 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center p-6 lg:p-12 text-center">
        <div className="flex items-center gap-3 mb-12">
          <div className="w-10 h-10 bg-[#E8527A] rounded-lg flex items-center justify-center">
            <Radio className="w-6 h-6 text-white" strokeWidth={1.5} />
          </div>
          <span className="text-2xl font-bold text-[#F5F5F0]">Spectriq</span>
        </div>

        <div className="text-[#E8527A] text-xs font-bold tracking-widest mb-4">WELCOME</div>

        <h1 className="text-5xl lg:text-6xl leading-tight font-bold text-[#F5F5F0] mb-6 tracking-tight max-w-3xl">
          Meetings, distilled.
        </h1>

        <p className="text-lg text-[#F5E6D3] leading-relaxed max-w-xl mb-10">
          Spectriq turns raw recordings into clear summaries, action items, and
          decisions — automatically.
        </p>

        <Link
          href="/sign-in"
          className="inline-flex items-center gap-2 px-8 py-3 rounded-lg bg-[#E8527A] text-white font-semibold hover:bg-[#d63f6f] transition-colors mb-16"
        >
          Sign in to get started <ArrowRight className="w-4 h-4" strokeWidth={2} />
        </Link>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl w-full">
          {features.map((feature, idx) => {
            const Icon = feature.icon
            return (
              <div
                key={idx}
                className="p-4 rounded-xl bg-[#141416] border border-[#2A2A2E] hover:border-[#E8527A] transition-colors text-left"
              >
                <Icon className="w-5 h-5 text-[#E8527A] mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-[#F5F5F0] mb-1">{feature.label}</h3>
                <p className="text-xs text-[#8A8A8E]">{feature.description}</p>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
