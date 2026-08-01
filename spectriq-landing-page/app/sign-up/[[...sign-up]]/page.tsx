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
        <SignUp
          routing="path"
          path="/sign-up"
          signInUrl="/sign-in"
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
              rootBox: 'w-full',
              cardBox: 'w-full shadow-none',
              card: 'w-full bg-[#141416] border border-[#2A2A2E] shadow-none backdrop-blur-0',
              header: 'backdrop-blur-0',
              main: 'backdrop-blur-0',
              socialButtonsBlockButton:
                '!bg-[#0A0A0B] !border !border-[#2A2A2E] !backdrop-blur-none !backdrop-filter-none !opacity-100',
              socialButtonsProviderIcon__google: 'opacity-100',
              socialButtonsBlockButtonText: '!text-[#F5F5F0] !opacity-100',
              dividerLine: 'bg-[#2A2A2E]',
              dividerText: 'text-[#8A8A8E]',
              footer: 'bg-[#141416] backdrop-blur-0',
              footerAction: 'bg-[#141416] backdrop-blur-0',
              footerActionText: 'text-[#8A8A8E]',
              footerActionLink: 'text-[#E8527A]',
              formFieldInput: 'bg-[#0A0A0B] border-[#2A2A2E] text-[#F5F5F0]',
              formFieldLabel: 'text-[#F5F5F0]',
              formButtonPrimary: 'bg-[#E8527A] hover:bg-[#d63f6f]',
            },
          }}
        />
      </div>
    </div>
  )
}
