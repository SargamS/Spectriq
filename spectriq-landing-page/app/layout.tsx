import { Analytics } from '@vercel/analytics/next'
import { ClerkProvider } from '@clerk/nextjs'
import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Spectriq - AI Meeting Summarizer',
  description: 'Transform meetings into actionable insights with AI-powered transcription and summaries',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#0A0A0B',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: '#E8527A',
          colorBackground: '#141416',
          colorInputBackground: '#0A0A0B',
          colorInputText: '#F5F5F0',
          colorText: '#F5F5F0',
          colorTextSecondary: '#8A8A8E',
          borderRadius: '0.75rem',
        },
      }}
    >
      <html lang="en" className="bg-[#0A0A0B]">
        <body className="antialiased bg-[#0A0A0B] text-[#F5F5F0]">
          {children}
          {process.env.NODE_ENV === 'production' && <Analytics />}
        </body>
      </html>
    </ClerkProvider>
  )
}
