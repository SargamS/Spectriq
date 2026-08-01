'use client'

import { Radio, Link2, Sparkles, FolderOpen } from 'lucide-react'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth, SignIn } from '@clerk/nextjs'

// Split-screen landing + sign-in, matching the two-column reference design:
// left = branding/marketing, right = the actual Clerk sign-in card.
// routing="hash" lets <SignIn> render right here on "/" without needing
// its own dedicated route (the separate /sign-in page still exists too,
// for any direct links elsewhere in the app).
export default function LandingPage() {
  const router = useRouter()
  const { isSignedIn, isLoaded } = useAuth()

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      router.replace('/dashboard')
    }
  }, [isLoaded, isSignedIn, router])

  const steps = [
    {
      icon: Link2,
      title: 'UPLOAD A RECORDING',
      description: 'Drop in any meeting audio or video',
    },
    {
      icon: Sparkles,
      title: 'GET INSIGHTS',
      description: 'AI transcribes and summarizes instantly',
    },
    {
      icon: FolderOpen,
      title: 'EXPLORE & ASK',
      description: 'Chat with your meeting, export notes',
    },
  ]

  return (
    <div className="min-h-screen bg-[#0A0A0B] flex flex-col lg:flex-row">
      {/* Left: branding */}
      <div className="relative flex-1 flex flex-col justify-center px-8 py-16 lg:px-20 overflow-hidden">
        <div
          className="absolute inset-0 opacity-5 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, #F5F5F0 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />

        <div className="relative z-10 flex items-center gap-3 mb-16">
          <div className="w-10 h-10 bg-[#E8527A] rounded-lg flex items-center justify-center">
            <Radio className="w-6 h-6 text-white" strokeWidth={1.5} />
          </div>
          <span className="text-2xl font-bold text-[#F5F5F0]">Spectriq</span>
        </div>

        <div className="relative z-10 max-w-xl">
          <h1 className="text-5xl lg:text-6xl leading-tight font-bold text-[#F5F5F0] mb-6 tracking-tight">
            Meetings, distilled.
          </h1>

          <p className="text-lg text-[#8A8A8E] leading-relaxed mb-16">
            Spectriq turns raw recordings into clear summaries, action items, and
            decisions — automatically.
          </p>

          <div className="space-y-8">
            {steps.map((step, idx) => {
              const Icon = step.icon
              return (
                <div key={idx} className="flex items-start gap-4">
                  <div className="w-9 h-9 rounded-full bg-[#141416] border border-[#2A2A2E] flex items-center justify-center flex-shrink-0 text-sm font-bold text-[#F5F5F0]">
                    {idx + 1}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="w-4 h-4 text-[#E8527A]" strokeWidth={1.5} />
                      <h3 className="text-sm font-bold tracking-widest text-[#F5F5F0]">
                        {step.title}
                      </h3>
                    </div>
                    <p className="text-sm text-[#8A8A8E]">{step.description}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <p className="relative z-10 text-xs text-[#8A8A8E] mt-16 hidden lg:block">
          © 2026 Spectriq. AI-powered meeting intelligence.
        </p>
      </div>

      {/* Right: sign-in */}
      <div className="flex-1 flex items-center justify-center bg-[#0A0A0B] border-t lg:border-t-0 lg:border-l border-[#2A2A2E] p-6 py-16">
        <div className="w-full max-w-sm">
          <SignIn
            routing="hash"
            signUpUrl="/sign-up"
            fallbackRedirectUrl="/dashboard"
            appearance={{
              variables: {
                colorPrimary: '#E8527A',
                colorBackground: '#141416',
                colorText: '#F5F5F0',
                colorTextSecondary: '#8A8A8E',
                colorInputBackground: '#0A0A0B',
                colorInputText: '#F5F5F0',
                borderRadius: '0.5rem',
              },
              elements: {
                card: 'border border-[#2A2A2E] shadow-none',
              },
            }}
          />
        </div>
      </div>
    </div>
  )
}
