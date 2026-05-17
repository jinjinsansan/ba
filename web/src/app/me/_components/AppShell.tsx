'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import { createClient } from '@/lib/supabase-browser'

type MenuItem = {
  href: string
  label: string
  icon: string
}

type Props = {
  userEmail: string
  isAdmin: boolean
  isSuspended: boolean
  isFree: boolean
  children: React.ReactNode
}

const USER_MENU: MenuItem[] = [
  { href: '/me', label: 'マイページ', icon: '◆' },
  { href: '/me/realtime', label: 'ライブ運用', icon: '▲' },
  { href: '/me/balance', label: '残高・チャージ', icon: '$' },
  { href: '/me/settlements', label: '日次精算履歴', icon: '☰' },
  { href: '/me/telegram', label: 'Telegram 連携', icon: '✦' },
  { href: '/me/referral', label: '紹介プログラム', icon: '✚' },
  { href: '/me/download', label: 'ダウンロード', icon: '⤓' },
  { href: '/me/support', label: 'サポート', icon: '?' },
]

export default function AppShell({ userEmail, isAdmin, isSuspended, isFree, children }: Props) {
  const pathname = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/')
    router.refresh()
  }

  const sidebar = (
    <aside className="h-full w-full md:w-64 glass-panel border-r border-accent/15 flex flex-col">
      <div className="px-6 py-5 border-b border-accent/10">
        <Link href="/me" onClick={() => setOpen(false)} className="text-sm font-hud tracking-[0.35em] text-accent block">
          BAFATHER
        </Link>
        <div className="text-[10px] tracking-widest text-text-dim mt-1 uppercase">Member Console</div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {USER_MENU.map(item => {
          const active = pathname === item.href || (item.href !== '/me' && pathname?.startsWith(item.href + '/'))
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                active
                  ? 'bg-accent/15 text-accent border border-accent/30'
                  : 'text-text-muted hover:text-text hover:bg-bg-glass'
              }`}
            >
              <span className="w-5 text-center font-mono text-xs">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          )
        })}

        {isAdmin && (
          <div className="pt-3 mt-3 border-t border-accent/10">
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-yellow-400 hover:bg-yellow-500/10 transition"
            >
              <span className="w-5 text-center font-mono text-xs">⚙</span>
              <span>Admin</span>
            </Link>
          </div>
        )}
      </nav>

      <div className="px-4 py-4 border-t border-accent/10 space-y-2">
        <div className="text-[11px] text-text-muted break-all leading-tight">{userEmail}</div>
        <div className="flex gap-1 flex-wrap">
          {isFree && <span className="text-[9px] tracking-widest bg-accent/20 text-accent px-1.5 py-0.5 rounded uppercase">Free</span>}
          {isSuspended && <span className="text-[9px] tracking-widest bg-banker/20 text-banker px-1.5 py-0.5 rounded uppercase">Locked</span>}
        </div>
        <button
          onClick={handleLogout}
          className="w-full text-xs text-text-muted hover:text-banker border border-accent/15 hover:border-banker/40 rounded-lg py-2 transition"
        >
          ログアウト
        </button>
      </div>
    </aside>
  )

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Mobile top bar */}
      <header className="md:hidden flex items-center justify-between glass-panel border-b border-accent/15 px-4 h-14 sticky top-0 z-30">
        <Link href="/me" className="text-xs font-hud tracking-[0.35em] text-accent">BAFATHER</Link>
        <button
          onClick={() => setOpen(true)}
          aria-label="open menu"
          className="text-text hover:text-accent text-xl px-2"
        >
          ☰
        </button>
      </header>

      {/* Desktop sidebar */}
      <div className="hidden md:block sticky top-0 h-screen">
        {sidebar}
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="w-64 h-full">{sidebar}</div>
          <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 min-w-0">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
          {children}
        </div>
      </main>
    </div>
  )
}
