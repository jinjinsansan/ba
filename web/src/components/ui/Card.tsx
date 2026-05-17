// components/ui/Card.tsx
import type { ReactNode } from 'react'

/**
 * Flat hairline card. No glow, no glass blur.
 * Use `padded={false}` when you need to put a CardHead + table inside.
 */
export function Card({
  children,
  className = '',
  padded = true,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <div
      className={[
        'bg-surface border border-white/[0.07] rounded-[10px]',
        padded ? 'p-5' : '',
        className,
      ].join(' ')}
    >
      {children}
    </div>
  )
}

/**
 * Section divider inside a (padded={false}) Card.
 * Left: small uppercase mono label.   Right: optional element.
 */
export function CardHead({
  children,
  right,
}: {
  children: ReactNode
  right?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.07]">
      <div className="font-mono text-[11px] text-text-muted tracking-[0.2em] uppercase">
        {children}
      </div>
      {right}
    </div>
  )
}
