'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import { createClient } from '@/lib/supabase-browser'

const ADMIN_MENU = [
  { href: '/admin', label: 'ダッシュボード', icon: '◆' },
  { href: '/admin/users', label: 'ユーザー', icon: '◇' },
  { href: '/admin/orders', label: '注文', icon: '$' },
  { href: '/admin/promos', label: 'プロモ', icon: '%' },
  { href: '/admin/tickets', label: 'チケット', icon: '?' },
  { href: '/admin/withdrawals', label: '出金申請', icon: '⤴' },
]

export default function AdminShell({ userEmail, children }: { userEmail: string; children: React.ReactNode }) {
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
    <aside className="h-full w-full md:w-64 glass-panel border-r border-yellow-500/30 flex flex-col">
      <div className="px-6 py-5 border-b border-yellow-500/20">
        <Link href="/admin" onClick={() => setOpen(false)} className="text-sm font-hud tracking-[0.35em] text-yellow-400 block">
          BAFATHER ⚙
        </Link>
        <div className="text-[10px] tracking-widest text-text-dim mt-1 uppercase">Admin Console</div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {ADMIN_MENU.map(item => {
          const active = pathname === item.href || (item.href !== '/admin' && pathname?.startsWith(item.href + '/'))
          const isUsers = item.href === '/admin/users'
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                active
                  ? 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30'
                  : 'text-text-muted hover:text-text hover:bg-bg-glass'
              }`}
            >
              <span className="w-5 text-center font-mono text-xs">{item.icon}</span>
              <span>{item.label}</span>
              {isUsers && pathname?.startsWith('/admin/users/') && pathname !== '/admin/users' && (
                <span className="ml-auto text-[9px] text-yellow-400">▼</span>
              )}
            </Link>
          )
        })}

        <div className="pt-3 mt-3 border-t border-accent/10">
          <Link
            href="/me"
            onClick={() => setOpen(false)}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-accent hover:bg-accent/10 transition"
          >
            <span className="w-5 text-center font-mono text-xs">←</span>
            <span>マイページに戻る</span>
          </Link>
        </div>
      </nav>

      <div className="px-4 py-4 border-t border-accent/10 space-y-2">
        <div className="text-[11px] text-text-muted break-all leading-tight">{userEmail}</div>
        <div className="text-[9px] tracking-widest bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded uppercase inline-block">Admin</div>
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
      <header className="md:hidden flex items-center justify-between glass-panel border-b border-yellow-500/30 px-4 h-14 sticky top-0 z-30">
        <Link href="/admin" className="text-xs font-hud tracking-[0.35em] text-yellow-400">BAFATHER ⚙</Link>
        <button onClick={() => setOpen(true)} aria-label="open menu" className="text-text hover:text-yellow-400 text-xl px-2">☰</button>
      </header>

      <div className="hidden md:block sticky top-0 h-screen">{sidebar}</div>

      {open && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="w-64 h-full">{sidebar}</div>
          <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
        </div>
      )}

      <main className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">{children}</div>
      </main>
    </div>
  )
}
