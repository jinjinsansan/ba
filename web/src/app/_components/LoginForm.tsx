'use client'

import Link from 'next/link'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase-browser'
import { Button } from '@/components/ui/Button'
import { Label } from '@/components/ui/PageHeader'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const supabase = createClient()
    const { error: loginError } = await supabase.auth.signInWithPassword({ email, password })
    if (loginError) {
      setError(loginError.message)
      setLoading(false)
    } else {
      router.push('/me')
      router.refresh()
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      <div
        aria-hidden
        className="absolute top-[30%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at center, rgba(92,223,255,0.06) 0%, transparent 70%)' }}
      />

      <div className="relative z-10 w-full max-w-[400px] bg-surface border border-white/[0.07] rounded-xl p-9 sm:p-10">
        <div className="text-center mb-8">
          <div className="font-hud text-[22px] font-bold text-cyan tracking-[0.18em] mb-1.5">BAFATHER</div>
          <div className="font-mono text-[10px] text-text-dim tracking-[0.3em] uppercase">Member Console · Sign In</div>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-md bg-lose/10 border border-lose/30 text-lose text-sm text-center">{error}</div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <Label>メールアドレス</Label>
            <input
              type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com"
              className="mt-1.5 w-full px-4 py-2.5 rounded-md bg-white/[0.02] border border-white/[0.07] text-text text-sm focus:outline-none focus:border-cyan-dim transition"
            />
          </div>

          <div>
            <Label>パスワード</Label>
            <input
              type="password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••"
              className="mt-1.5 w-full px-4 py-2.5 rounded-md bg-white/[0.02] border border-white/[0.07] text-text text-sm focus:outline-none focus:border-cyan-dim transition"
            />
          </div>

          <Button tone="primary" size="lg" type="submit" disabled={loading} className="w-full">
            {loading ? 'サインイン中...' : 'サインイン'}
          </Button>
        </form>

        <p className="mt-6 pt-5 border-t border-white/[0.07] text-center text-sm text-text-muted">
          アカウントをお持ちでない方は <Link href="/signup" className="text-cyan hover:underline">新規登録</Link>
        </p>
      </div>

      <div className="absolute bottom-5 left-0 right-0 text-center font-mono text-[10px] text-text-dim tracking-[0.3em] uppercase">
        v2.4.0 · ssl secured · bafather.uk
      </div>
    </div>
  )
}
