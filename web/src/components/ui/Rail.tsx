'use client'

// components/ui/Rail.tsx
// Member-side icon rail. Drop-in replacement for me/_components/AppShell.tsx
// Mobile: top bar + slide-in drawer (Esc closes, body scroll locked).

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState, type ReactNode } from 'react'
import { createClient } from '@/lib/supabase-browser'

type Item = { href: string; label: string; glyph: string }

const USER_MENU: Item[] = [
  { href: '/me',             label: 'Home',     glyph: '◆' },
  { href: '/me/realtime',    label: 'Live',     glyph: '▲' },
  { href: '/me/balance',     label: 'Balance',  glyph: '$' },
  { href: '/me/settlements', label: 'Settle',   glyph: '≡' },
  { href: '/me/telegram',    label: 'Telegram', glyph: '✦' },
  { href: '/me/referral',    label: 'Referral', glyph: '+' },
  { href: '/me/support',     label: 'Support',  glyph: '?' },
]

export default function Rail({
  userEmail,
  isAdmin,
  isSuspended,
  isFree,
  children,
}: {
  userEmail: string
  isAdmin: boolean
  isSuspended: boolean
  isFree: boolean
  children: ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)

  // Mobile drawer ergonomics
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
    if (href === '/me') return pathname === '/me'
    return pathname === href || pathname?.startsWith(href + '/')
  }

  const railContent = (
    <aside
      className="
        w-[72px] h-full flex-shrink-0
        bg-bg-rail border-r border-white/[0.07]
        flex flex-col pt-[18px] pb-3 gap-0.5
      "
    >
      {/* Brand */}
      <Link
        href="/me"
        onClick={() => setOpen(false)}
        className="block text-center font-hud text-[12px] font-bold text-cyan tracking-[0.15em] mb-[18px]"
      >
        BF
      </Link>

      {USER_MENU.map(it => {
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
                active ? 'bg-cyan' : 'bg-transparent',
              ].join(' ')}
            />
            <div className="font-mono text-sm leading-none">{it.glyph}</div>
            <div
              className={[
                'font-mono text-[9px] mt-1 tracking-[0.08em] uppercase',
                active ? 'text-cyan' : 'text-text-dim',
              ].join(' ')}
            >
              {it.label}
            </div>
          </Link>
        )
      })}

      {isAdmin && (
        <Link
          href="/admin"
          onClick={() => setOpen(false)}
          className="relative py-2.5 pb-1.5 text-center text-amber hover:brightness-110 mt-2 border-t border-white/[0.06] pt-3"
        >
          <div className="font-mono text-sm leading-none">⚙</div>
          <div className="font-mono text-[9px] mt-1 tracking-[0.08em] uppercase text-amber">Admin</div>
        </Link>
      )}

      <div className="flex-1" />

      {/* Avatar / logout */}
      <button
        onClick={handleLogout}
        title={userEmail}
        aria-label={`Sign out (${userEmail})`}
        className="
          mx-auto w-8 h-8 rounded-full
          bg-surface-2 border border-white/[0.07]
          flex items-center justify-center
          font-mono text-[11px] text-text-muted
          hover:text-text hover:border-white/[0.14] transition
        "
      >
        {(userEmail || '?')[0]?.toLowerCase()}
      </button>
      <div className="mt-1 flex flex-col items-center gap-0.5">
        {isFree && <span className="font-mono text-[8px] tracking-[0.1em] text-cyan">FREE</span>}
        {isSuspended && <span className="font-mono text-[8px] tracking-[0.1em] text-lose">LOCK</span>}
      </div>
    </aside>
  )

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Mobile top bar */}
      <header
        className="
          md:hidden sticky top-0 z-30 h-14
          flex items-center justify-between px-4
          bg-bg-rail border-b border-white/[0.07]
        "
      >
        <Link href="/me" className="font-hud text-[13px] tracking-[0.2em] text-cyan font-bold">
          BAFATHER
        </Link>
        <button
          aria-label="メニューを開く"
          aria-expanded={open}
          aria-controls="member-rail"
          onClick={() => setOpen(true)}
          className="text-text hover:text-cyan p-2 -mr-2"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      {/* Desktop rail */}
      <div className="hidden md:block sticky top-0 h-screen" id="member-rail">
        {railContent}
      </div>

      {/* Mobile drawer */}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="ナビゲーション"
          className="md:hidden fixed inset-0 z-40 flex"
        >
          <div
            className="
              w-[72px] h-full
              transform transition-transform duration-200 ease-out
              translate-x-0
            "
          >
            {railContent}
          </div>
          <div
            className="flex-1 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
        </div>
      )}

      <main className="flex-1 min-w-0">
        <div className="max-w-5xl mx-auto px-4 sm:px-8 py-6 sm:py-9">{children}</div>
      </main>
    </div>
  )
}
