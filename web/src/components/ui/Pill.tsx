// components/ui/Pill.tsx
import type { ReactNode } from 'react'

type Tone =
  | 'live'    // 緑 — ACTIVE / paid / confirmed
  | 'warn'    // 橙 — pending / unpaid
  | 'danger'  // 赤 — destructive / suspended / rejected
  | 'info'    // cyan — neutral info
  | 'free'    // cyan強め — FREE プラン
  | 'admin'   // amber — 管理者識別
  | 'paid'    // muted — 完了したが目立たせない
  | 'mute'

const TONES: Record<Tone, string> = {
  live:   'text-win    bg-win/10    border-win/30',
  warn:   'text-warn   bg-warn/10   border-warn/30',
  danger: 'text-lose   bg-lose/10   border-lose/30',
  info:   'text-cyan   bg-cyan/10   border-cyan/25',
  free:   'text-cyan   bg-cyan/15   border-cyan/40',
  admin:  'text-amber  bg-amber/10  border-amber/30',
  paid:   'text-text-muted bg-white/[0.04] border-white/10',
  mute:   'text-text-muted bg-white/[0.04] border-white/10',
}

export function Pill({
  tone = 'info',
  dot = false,
  children,
}: {
  tone?: Tone
  dot?: boolean
  children: ReactNode
}) {
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 whitespace-nowrap',
        'font-mono text-[11px] tracking-[0.08em]',
        'px-2 py-0.5 rounded border leading-none',
        TONES[tone],
      ].join(' ')}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}
