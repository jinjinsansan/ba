'use client'

// components/dashboard/ChargeMeter.tsx
// 今週のチャージ見込みメーター(リデザイン 2026-08 / 案1a)。
// 表示ルール(ハンドオフ説明書4):
//   weeklyNetProfit - carryLoss <= 0 → 「$0」+「今週の請求はありません」
//   それ以外                         → (weeklyNetProfit - carryLoss) * shareRate

import { useTranslations } from 'next-intl'

export type ChargeMeterProps = {
  weeklyNetProfit: number  // 今週の純利益(USD)。マイナス可
  shareRate: number        // 0.30
  carryLoss: number        // 繰越損失(USD, >= 0)
  weekEndsAt: string       // ISO 8601 / 土曜 23:59 JST
  daily: { day: 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat'; pnl: number }[]
}

const DAY_ORDER: ChargeMeterProps['daily'][number]['day'][] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat']

function usd(n: number) {
  const sign = n < 0 ? '−' : ''
  return `${sign}$${Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

export default function ChargeMeter({ weeklyNetProfit, shareRate, carryLoss, weekEndsAt, daily }: ChargeMeterProps) {
  const t = useTranslations('widgets.chargeMeter')
  const deadline = (() => {
    try {
      return new Date(weekEndsAt).toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })
    } catch {
      return ''
    }
  })()
  const billable = weeklyNetProfit - carryLoss
  const noCharge = billable <= 0
  const fee = noCharge ? 0 : billable * shareRate
  const remainToResume = noCharge ? Math.max(0, carryLoss - Math.max(0, weeklyNetProfit)) : 0

  const byDay = new Map(daily.map(d => [d.day, d.pnl]))
  const maxAbs = Math.max(1, ...daily.map(d => Math.abs(d.pnl)))

  return (
    <div className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col md:flex-row gap-7 md:items-center">
      <div className="flex-1 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[15px] text-text-muted">{t('title')}</span>
          <span
            title={t('tooltip')}
            className="w-[17px] h-[17px] rounded-full border border-white/20 text-text-dim text-[11px] inline-flex items-center justify-center cursor-help"
          >
            ?
          </span>
        </div>
        <div className="flex items-baseline gap-3.5 flex-wrap">
          <span className="font-mono tabular-nums text-[48px] sm:text-[56px] font-bold tracking-tight leading-none">
            ${Math.round(fee).toLocaleString('en-US')}
          </span>
          <span className="text-base text-text-muted">
            {noCharge ? t('noChargeThisWeek') : t('billedSunday')}
          </span>
        </div>
        {noCharge && carryLoss > 0 ? (
          <p className="text-sm text-text-muted leading-relaxed m-0">
            {t.rich('carryBody', {
              carry: (c) => <span className="font-mono tabular-nums text-warn">{c}</span>,
              remain: (c) => <span className="font-mono tabular-nums text-text font-semibold">{c}</span>,
              carryValue: usd(carryLoss),
              remainValue: usd(remainToResume),
            })}
          </p>
        ) : (
          <div className="text-sm text-text-dim">
            {t.rich('formula', {
              profit: (c) => (
                <span className={['font-mono tabular-nums', weeklyNetProfit >= 0 ? 'text-win' : 'text-lose'].join(' ')}>
                  {c}
                </span>
              ),
              profitValue: `${weeklyNetProfit >= 0 ? '+' : ''}${usd(weeklyNetProfit)}`,
              rate: Math.round(shareRate * 100),
              deadline,
            })}
          </div>
        )}
      </div>

      <div className="w-full md:w-[300px] flex flex-col gap-2.5">
        <div className="flex items-end gap-2 h-[76px]">
          {DAY_ORDER.map(day => {
            const pnl = byDay.get(day)
            const has = pnl !== undefined && pnl !== 0
            const h = has ? Math.max(6, (Math.abs(pnl!) / maxAbs) * 64) : 6
            return (
              <div key={day} className="flex-1 flex flex-col items-center gap-1.5">
                <div
                  className={[
                    'w-full rounded',
                    !has ? 'bg-white/[0.09]' : pnl! > 0 ? 'bg-win/50' : 'bg-lose/50',
                  ].join(' ')}
                  style={{ height: `${h}px` }}
                />
                <span className="text-[11px] text-text-dim">{t(`days.${day}`)}</span>
              </div>
            )
          })}
        </div>
        <div className="text-[13px] text-text-dim">
          {carryLoss > 0 ? t('footerWithCarry') : t('footerNoCarry')}
        </div>
      </div>
    </div>
  )
}
