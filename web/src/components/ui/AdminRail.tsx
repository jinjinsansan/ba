'use client'

// components/ui/AdminRail.tsx
// Admin-side icon rail. Drop-in replacement for admin/_components/AdminShell.tsx
// Uses amber as the admin identity color (replaces former yellow-500).

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState, type ReactNode } from 'react'
import { createClient } from '@/lib/supabase-browser'

const ADMIN_MENU = [
  { href: '/admin',             label: 'Dashboard', glyph: '◆' },
  { href: '/admin/users',       label: 'Users',     glyph: '◇' },
  { href: '/admin/orders',      label: 'Orders',    glyph: '$' },
  { href: '/admin/promos',      label: 'Promos',    glyph: '%' },
  { href: '/admin/tickets',     label: 'Tickets',   glyph: '?' },
  { href: '/admin/withdrawals', label: 'Withdraw',  glyph: '⤴' },
]

export default function AdminRail({
  userEmail,
  children,
}: {
  userEmail: string
  children: ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open])

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/')
    router.refresh()
  }

  function isActive(href: string) {
    if (href === '/admin') return pathname === '/admin'
    return pathname === href || pathname?.startsWith(href + '/')
  }

  const rail = (
    <aside
      className="
        w-[72px] h-full flex-shrink-0
        bg-bg-rail border-r border-white/[0.07]
        flex flex-col pt-[18px] pb-3 gap-0.5
      "
    >
      <Link
        href="/admin"
        onClick={() => setOpen(false)}
        className="block text-center font-hud text-[11px] font-bold text-amber tracking-[0.15em]"
      >
        BF
      </Link>
      <div className="text-center font-mono text-[8px] tracking-[0.2em] text-amber-dim mb-3.5">
        ADMIN
      </div>

      {ADMIN_MENU.map(it => {
        const active = isActive(it.href)
        return (
          <Link
            key={it.href}
            href={it.href}
            onClick={() => setOpen(false)}
            className={[
              'relative py-2.5 pb-1.5 text-center transition',
              active ? 'text-text' : 'text-text-dim hover:text-text',
            ].join(' ')}
          >
            <span
              aria-hidden
              className={[
                'absolute left-0 top-1.5 bottom-1 w-[2px] rounded-r',
                active ? 'bg-amber' : 'bg-transparent',
              ].join(' ')}
            />
            <div className="font-mono text-sm leading-none">{it.glyph}</div>
            <div
              className={[
                'font-mono text-[9px] mt-1 tracking-[0.08em] uppercase',
                active ? 'text-amber' : 'text-text-dim',
              ].join(' ')}
            >
              {it.label}
            </div>
          </Link>
        )
      })}

      <Link
        href="/me"
        onClick={() => setOpen(false)}
        className="relative py-2.5 pb-1.5 text-center text-cyan hover:brightness-110 mt-2 border-t border-white/[0.06] pt-3"
      >
        <div className="font-mono text-sm leading-none">←</div>
        <div className="font-mono text-[9px] mt-1 tracking-[0.08em] uppercase text-cyan">User</div>
      </Link>

      <div className="flex-1" />

      <button
        onClick={handleLogout}
        title={userEmail}
        aria-label={`Sign out (${userEmail})`}
        className="
          mx-auto w-8 h-8 rounded-full
          bg-amber/10 border border-amber/30
          flex items-center justify-center
          font-mono text-[11px] text-amber
          hover:brightness-110 transition
        "
      >
        ⚙
      </button>
    </aside>
  )

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <header
        className="
          md:hidden sticky top-0 z-30 h-14
          flex items-center justify-between px-4
          bg-bg-rail border-b border-white/[0.07]
        "
      >
        <Link href="/admin" className="font-hud text-[13px] tracking-[0.2em] text-amber font-bold">
          BAFATHER · ADMIN
        </Link>
        <button
          aria-label="メニューを開く"
          aria-expanded={open}
          onClick={() => setOpen(true)}
          className="text-text hover:text-amber p-2 -mr-2"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      <div className="hidden md:block sticky top-0 h-screen">{rail}</div>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Admin navigation"
          className="md:hidden fixed inset-0 z-40 flex"
        >
          <div className="w-[72px] h-full">{rail}</div>
          <div className="flex-1 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
        </div>
      )}

      <main className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6 sm:py-9">{children}</div>
      </main>
    </div>
  )
}
