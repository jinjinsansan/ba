'use client'

// app/_components/LoginForm.tsx — V2 right-side form
//
// Same supabase auth flow as the existing file. Rewritten chrome to fit
// inside the V2 split layout (LoginPage). Stretches to fill its grid column
// and centers the form vertically. On mobile (when OperatorWall is hidden)
// it occupies the full viewport.

import Link from 'next/link'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase-browser'
import { Button } from '@/components/ui/Button'
import { Label } from '@/components/ui/PageHeader'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
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
    <div className="min-h-screen lg:min-h-0 flex items-center justify-center bg-bg p-8 sm:p-14 lg:p-14 relative">
      <div className="w-full max-w-[360px]">
        {/* Heading */}
        <div className="mb-8">
          <div className="font-mono text-[10px] text-cyan tracking-[0.3em] uppercase mb-2 flex items-center gap-2">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan" />
            Operator Sign In
          </div>
          <h1 className="text-[26px] font-bold tracking-[-0.01em] m-0">
            おかえりなさい
          </h1>
          <div className="text-text-muted text-[13px] mt-1.5">
            アカウント情報でサインインしてください
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-md bg-lose/10 border border-lose/30 text-lose text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <Label>メールアドレス</Label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="
                mt-1.5 w-full px-3.5 py-2.5 rounded-md
                bg-white/[0.02] border border-white/[0.07]
                text-text text-sm
                focus:outline-none focus:border-cyan-dim
                transition
              "
            />
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <Label>パスワード</Label>
              <Link href="/forgot" className="text-[11px] text-cyan hover:underline">
                忘れた
              </Link>
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="
                w-full px-3.5 py-2.5 rounded-md
                bg-white/[0.02] border border-white/[0.07]
                text-text text-sm
                focus:outline-none focus:border-cyan-dim
                transition
              "
            />
          </div>

          <label className="flex items-center gap-2.5 text-[13px] text-text-muted cursor-pointer select-none pt-2 pb-1">
            <input
              type="checkbox"
              checked={remember}
              onChange={e => setRemember(e.target.checked)}
              className="sr-only"
            />
            <span
              aria-hidden
              className={`
                inline-flex items-center justify-center
                w-[14px] h-[14px] rounded-[3px] text-[10px]
                transition
                ${remember
                  ? 'bg-cyan/10 border border-cyan-dim text-cyan'
                  : 'bg-transparent border border-white/[0.15] text-transparent'
                }
              `}
            >
              ✓
            </span>
            このデバイスを記憶する
          </label>

          <Button tone="primary" size="lg" type="submit" disabled={loading} className="w-full">
            {loading ? 'サインイン中...' : 'サインイン →'}
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-white/[0.07] text-center text-sm text-text-muted">
          アカウントをお持ちでない方は{' '}
          <Link href="/signup" className="text-cyan hover:underline">
            新規登録 →
          </Link>
        </div>

        {/* Mobile-only mini trust strip (hidden on lg where the wall shows it) */}
        <div className="lg:hidden mt-10 flex justify-center gap-5 font-mono text-[10px] text-text-dim tracking-[0.2em] uppercase">
          <span>● SSL</span>
          <span>● 2FA</span>
          <span>● 24/7 JST</span>
        </div>
      </div>
    </div>
  )
}
