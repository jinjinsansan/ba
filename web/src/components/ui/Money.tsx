// components/ui/Money.tsx
import type { ReactNode } from 'react'

/**
 * Numeric display with mono + tabular-nums for clean column alignment.
 *
 *   <Money value={1234.5} />               => $1,234.50
 *   <Money value={-58} sign size="3xl" tone="lose" />   => -$58.00
 *   <Money value="—" />                    => — (literal passthrough)
 */
export function Money({
  value,
  sign = false,
  size = 'lg',
  weight = 'semibold',
  tone,
  children,
}: {
  value?: number | string | null
  sign?: boolean
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl'
  weight?: 'normal' | 'medium' | 'semibold' | 'bold'
  tone?: 'win' | 'lose' | 'cyan' | 'amber' | 'warn' | 'muted' | 'dim'
  children?: ReactNode
}) {
  const sizes: Record<string, string> = {
    sm:   'text-sm',
    md:   'text-base',
    lg:   'text-lg',
    xl:   'text-xl',
    '2xl':'text-[28px] leading-none',
    '3xl':'text-[42px] leading-none',
  }
  const weights: Record<string, string> = {
    normal:   'font-normal',
    medium:   'font-medium',
    semibold: 'font-semibold',
    bold:     'font-bold',
  }
  const tones: Record<string, string> = {
    win:    'text-win',
    lose:   'text-lose',
    cyan:   'text-cyan',
    amber:  'text-amber',
    warn:   'text-warn',
    muted:  'text-text-muted',
    dim:    'text-text-dim',
  }

  const formatted = (() => {
    if (children) return children
    if (value === null || value === undefined) return '—'
    if (typeof value === 'string') return value
    const n = Number(value)
    if (!Number.isFinite(n)) return '—'
    const abs = Math.abs(n).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    if (sign && n > 0) return `+$${abs}`
    if (n < 0)         return `-$${abs}`
    return `$${abs}`
  })()

  return (
    <span
      className={[
        'font-mono num tabular-nums',
        sizes[size],
        weights[weight],
        tone ? tones[tone] : 'text-text',
      ].join(' ')}
    >
      {formatted}
    </span>
  )
}
