import { SignUp } from '@clerk/nextjs'
import { Radio } from 'lucide-react'

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center p-6">
      <div className="w-full max-w-sm flex flex-col items-center">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-[#E8527A] rounded-lg flex items-center justify-center">
            <Radio className="w-6 h-6 text-white" strokeWidth={1.5} />
          </div>
          <span className="text-2xl font-bold text-[#F5F5F0]">Spectriq</span>
        </div>
        <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/dashboard" />
      </div>
    </div>
  )
}
