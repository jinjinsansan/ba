'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase-browser'

export default function LoginPage() {
  const t = useTranslations('auth')
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
      router.push('/dashboard')
      router.refresh()
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 sm:px-6">
      <div className="w-full max-w-md glass-card p-6 sm:p-8">
        <div className="hud-label text-center mb-2">{t('accessLabel')}</div>
        <h1 className="text-2xl sm:text-3xl font-black text-center mb-2 font-hud">{t('login.title')}</h1>
        <p className="text-center text-sm sm:text-base text-text-muted mb-8">{t('login.subtitle')}</p>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-banker/10 border border-banker/30 text-banker text-sm text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm text-text-muted mb-1">{t('login.email')}</label>
            <input
              type="email" required value={email} onChange={e => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition text-sm sm:text-base"
              placeholder={t('login.emailPlaceholder')}
            />
          </div>
          <div>
            <label className="block text-sm text-text-muted mb-1">{t('login.password')}</label>
            <input
              type="password" required value={password} onChange={e => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition text-sm sm:text-base"
              placeholder={t('login.passwordPlaceholder')}
            />
          </div>
          <button
            type="submit" disabled={loading}
            className="w-full btn-primary py-3 disabled:opacity-50"
          >
            {loading ? t('login.submitting') : t('login.submit')}
          </button>
        </form>

        <p className="text-center text-sm text-text-muted mt-6">
          {t('login.noAccount')} <Link href="/signup" className="text-accent hover:underline">{t('login.signupLink')}</Link>
        </p>
      </div>
    </div>
  )
}
