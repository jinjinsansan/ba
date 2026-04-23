'use client'

import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase-browser'

export default function DashboardClient() {
  const t = useTranslations('dashboard')
  const router = useRouter()

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  return (
    <button onClick={handleLogout} className="text-sm text-text-muted hover:text-text transition">
      {t('logout')}
    </button>
  )
}
