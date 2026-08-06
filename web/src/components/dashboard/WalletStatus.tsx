'use client'

// components/dashboard/WalletStatus.tsx
// ウォレット突合ステータス(リデザイン 2026-08 / 案1a)。4状態はハンドオフ説明書4のとおり。

import Link from 'next/link'
import { useTranslations } from 'next-intl'

export type WalletStatusProps = {
  status: 'matched' | 'checking' | 'mismatched' | 'unregistered'
  address?: string         // 表示は先頭4文字…末尾4文字
  network?: 'tron' | 'bsc'
  lastCheckedAt?: string   // ISO 8601
}

const TONES: Record<WalletStatusProps['status'], { box: string; icon: string; glyph: string }> = {
  matched:      { box: 'border-win/[0.22]',      icon: 'bg-win/[0.12] text-win',   glyph: '✓' },
  checking:     { box: 'border-warn/[0.22]',     icon: 'bg-warn/[0.12] text-warn', glyph: '◷' },
  mismatched:   { box: 'border-lose/[0.22]',     icon: 'bg-lose/[0.12] text-lose', glyph: '!' },
  unregistered: { box: 'border-white/[0.07]',    icon: 'bg-white/[0.05] text-text-dim', glyph: '–' },
}

function shortAddr(a?: string) {
  if (!a || a.length < 10) return a || ''
  return `${a.slice(0, 4)}…${a.slice(-4)}`
}

function fmtTime(iso?: string) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export default function WalletStatus({ status, address, network, lastCheckedAt }: WalletStatusProps) {
  const t = useTranslations('widgets.walletStatus')
  const tone = TONES[status]
  const time = fmtTime(lastCheckedAt)

  return (
    <div className={['bg-surface border rounded-2xl px-6 py-5 flex items-center gap-4', tone.box].join(' ')}>
      <span className={['flex-none w-9 h-9 rounded-[10px] flex items-center justify-center text-[17px] font-bold', tone.icon].join(' ')}>
        {tone.glyph}
      </span>
      <div className="flex-1 min-w-0">
        <div className={['text-base font-semibold', status === 'unregistered' ? 'text-text-muted' : 'text-text'].join(' ')}>
          {t(`${status}.title`)}
        </div>
        <div className="text-sm text-text-muted mt-0.5">
          {t(`${status}.body`)}
          {time && status !== 'unregistered' ? ` ${t('lastChecked', { time })}` : ''}
        </div>
      </div>
      {status === 'unregistered' ? (
        <Link
          href="/me/wallet"
          className="flex-none border border-cyan/40 text-cyan text-sm font-semibold rounded-lg px-3.5 py-2 hover:bg-cyan/10 transition"
        >
          {t('registerCta')}
        </Link>
      ) : address ? (
        <span className="flex-none font-mono tabular-nums text-[13px] text-text-dim" title={network === 'bsc' ? 'BNB Chain' : 'TRON'}>
          {shortAddr(address)}
        </span>
      ) : null}
    </div>
  )
}
