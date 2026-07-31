import { SignIn } from '@clerk/nextjs'
import { Radio, Shield } from 'lucide-react'

// Real sign-in, delegated entirely to Clerk (Google OAuth + email code/
// password, however you configure it in the Clerk dashboard). This replaces
// the old landing-page form that collected an email + password and never
// actually checked the password against anything.
export default function SignInPage() {
  return (
    <div className="min-h-screen bg-[#0A0A0B] relative overflow-hidden">
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: 'radial-gradient(circle, #F5F5F0 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <div className="relative z-10 flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-sm flex flex-col items-center">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-[#E8527A] rounded-lg flex items-center justify-center">
              <Radio className="w-6 h-6 text-white" strokeWidth={1.5} />
            </div>
            <span className="text-2xl font-bold text-[#F5F5F0]">Spectriq</span>
          </div>

          <SignIn
            routing="path"
            path="/sign-in"
            signUpUrl="/sign-up"
            fallbackRedirectUrl="/dashboard"
          />

          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-[#8A8A8E]">
            <Shield className="w-4 h-4 text-[#E8527A]" strokeWidth={1.5} />
            <span>Your recordings are processed securely and never shared.</span>
          </div>
        </div>
      </div>
    </div>
  )
}
