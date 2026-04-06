'use client'

import { Suspense, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { createClient } from '@/lib/supabase-browser'

function SignupForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [referralCode, setReferralCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const searchParams = useSearchParams()
  const plan = searchParams.get('plan')

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')

    const supabase = createClient()
    const { error: signupError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=${plan ? `/purchase?plan=${plan}` : '/dashboard'}`,
        data: { referred_by: referralCode || null },
      },
    })

    if (signupError) {
      setError(signupError.message)
    } else {
      setMessage('Check your email for a confirmation link.')
    }
    setLoading(false)
  }

  return (
    <div className="w-full max-w-md">
      <h1 className="text-3xl font-black text-center mb-2">Create Account</h1>
      <p className="text-center text-slate-400 mb-8">Join LAPLACE and start winning</p>

      {message && (
        <div className="mb-6 p-4 rounded-xl bg-player/10 border border-player/30 text-player text-sm text-center">
          {message}
        </div>
      )}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-banker/10 border border-banker/30 text-banker text-sm text-center">
          {error}
        </div>
      )}

      <form onSubmit={handleSignup} className="space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Email</label>
          <input
            type="email" required value={email} onChange={e => setEmail(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Password</label>
          <input
            type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition"
            placeholder="Min 8 characters"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Referral Code <span className="text-slate-600">(optional)</span></label>
          <input
            type="text" value={referralCode} onChange={e => setReferralCode(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition"
            placeholder="REF-XXXXXXXX"
          />
        </div>
        <button
          type="submit" disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold hover:opacity-90 transition disabled:opacity-50"
        >
          {loading ? 'Creating...' : 'Create Account'}
        </button>
      </form>

      <p className="text-center text-sm text-slate-500 mt-6">
        Already have an account? <Link href="/login" className="text-player hover:underline">Login</Link>
      </p>
    </div>
  )
}

export default function SignupPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <Suspense fallback={<div className="text-slate-400">Loading...</div>}>
        <SignupForm />
      </Suspense>
    </div>
  )
}
