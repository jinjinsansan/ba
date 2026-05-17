// components/ui/PageHeader.tsx
import type { ReactNode } from 'react'

/**
 * Standard page header for every console page.
 *
 * kicker  : small uppercase Latin label  (e.g. "Member · Home")
 * title   : page title (Japanese OK — uses body font, not Orbitron)
 * sub     : muted description line
 * right   : optional right-aligned element (status pill, action button)
 */
export function PageHeader({
  kicker,
  title,
  sub,
  right,
}: {
  kicker?: string
  title: string
  sub?: string
  right?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div className="min-w-0">
        {kicker && (
          <div className="font-mono text-[11px] text-text-dim tracking-[0.25em] uppercase">
            {kicker}
          </div>
        )}
        <h1 className="text-2xl sm:text-[28px] font-bold tracking-[-0.01em] mt-1.5 leading-tight">
          {title}
        </h1>
        {sub && <div className="text-sm text-text-muted mt-1.5">{sub}</div>}
      </div>
      {right}
    </header>
  )
}

/**
 * Standalone HUD kicker — use when you need a divider label
 * (e.g. before a 2nd grid section on the same page).
 */
export function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[11px] text-text-dim tracking-[0.25em] uppercase">
      {children}
    </div>
  )
}

/**
 * Small uppercase label used inside cards (above values).
 */
export function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">
      {children}
    </div>
  )
}
