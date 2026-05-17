// components/ui/Button.tsx
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Tone =
  | 'primary'     // cyan fill, ページ最重要 CTA
  | 'secondary'   // surface fill, 二次操作
  | 'ghost'       // text only
  | 'outline'     // cyan stroke, 強調された secondary
  | 'danger'      // 破壊的操作 (suspend, reject, delete)
  | 'success'     // confirm / approve

type Size = 'sm' | 'md' | 'lg'

const TONES: Record<Tone, string> = {
  primary:
    'bg-cyan text-[#001721] font-semibold hover:brightness-110',
  secondary:
    'bg-white/[0.05] text-text border border-white/[0.07] hover:bg-white/[0.08]',
  ghost:
    'bg-transparent text-text-muted hover:text-text hover:bg-white/[0.04]',
  outline:
    'bg-transparent text-cyan border border-cyan-dim hover:border-cyan',
  danger:
    'bg-transparent text-lose border border-lose/40 hover:bg-lose/10',
  success:
    'bg-transparent text-win border border-win/40 hover:bg-win/10',
}

const SIZES: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-sm',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: Tone
  size?: Size
  children: ReactNode
}

export function Button({
  tone = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      className={[
        'inline-flex items-center justify-center gap-2',
        'rounded-md transition',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        TONES[tone],
        SIZES[size],
        className,
      ].join(' ')}
    >
      {children}
    </button>
  )
}
