'use client'

// components/dashboard/SubscriptionCard.tsx
// サブスク残り日数カード(リデザイン 2026-08 / 案1a)。
// 表示のみ。期限データの配線は後工程 — 呼び出し側が TODO: wire real data を持つ。

import Link from 'next/link'
import { useTranslations } from 'next-intl'

export type SubscriptionCardProps = {
  expiresAt: string        // ISO 8601
  daysLeft: number         // 0 以下なら「期限切れ」表示に切替
  totalDays?: number       // 既定 30。進捗バーの分母
}

function fmtDate(iso: string, locale: string) {
  try {
    return new Date(iso).toLocaleDateString(locale, { month: 'long', day: 'numeric' })
  } catch {
    return iso
  }
}

export default function SubscriptionCard({ expiresAt, daysLeft, totalDays = 30 }: SubscriptionCardProps) {
  const t = useTranslations('widgets.subscription')
  const expired = daysLeft <= 0
  const pct = Math.max(0, Math.min(100, (daysLeft / totalDays) * 100))
  const nearExpiry = !expired && daysLeft <= 3

  return (
    <div
      className={[
        'bg-surface border rounded-2xl p-6 flex flex-col gap-3.5',
        expired ? 'border-lose/30' : nearExpiry ? 'border-warn/30' : 'border-white/[0.07]',
      ].join(' ')}
    >
      <div className="flex justify-between items-center">
        <span className="text-[15px] text-text-muted">{t('title')}</span>
        {!expired && (
          <span className="text-[13px] text-text-dim">{t('until', { date: fmtDate(expiresAt, 'ja-JP') })}</span>
        )}
      </div>

      {expired ? (
        <>
          <div className="text-[28px] font-bold text-lose leading-tight">{t('expired')}</div>
          <p className="text-sm text-text-muted leading-relaxed m-0">{t('expiredBody')}</p>
          <Link
            href="/purchase"
            className="self-start bg-cyan text-[#001721] font-bold text-[15px] rounded-xl px-6 py-3.5 hover:brightness-110 transition"
          >
            {t('renewCta')}
          </Link>
        </>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="font-mono tabular-nums text-[52px] sm:text-[60px] font-bold tracking-tight leading-none">
              {daysLeft}
            </span>
            <span className="text-xl text-text-muted">{t('daysUnit')}</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/[0.07] overflow-hidden">
            <div
              className={['h-full', nearExpiry ? 'bg-warn' : 'bg-cyan'].join(' ')}
              style={{ width: `${pct}%` }}
            />
          </div>
          {nearExpiry && (
            <Link href="/purchase" className="text-sm text-warn hover:brightness-110 transition">
              {t('nearExpiry')}
            </Link>
          )}
        </>
      )}
    </div>
  )
}
