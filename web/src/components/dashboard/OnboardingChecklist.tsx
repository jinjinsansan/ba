'use client'

// components/dashboard/OnboardingChecklist.tsx
// はじめの設定チェックリスト(リデザイン 2026-08)。
// 全 done なら null を返す(カードごと非表示 — ハンドオフ説明書3.3)。

import Link from 'next/link'
import { useTranslations } from 'next-intl'

export type OnboardingChecklistProps = {
  steps: { id: 'subscription' | 'wallet' | 'gui'; done: boolean; href: string }[]
}

export default function OnboardingChecklist({ steps }: OnboardingChecklistProps) {
  const t = useTranslations('widgets.onboarding')
  const doneCount = steps.filter(s => s.done).length
  if (doneCount === steps.length) return null

  const pct = Math.round((doneCount / steps.length) * 100)
  const next = steps.find(s => !s.done)

  return (
    <div className="bg-surface border border-cyan/[0.22] rounded-2xl p-6 flex flex-col gap-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <div className="text-[17px] font-bold">
          {t('title')}{' '}
          <span className="font-mono tabular-nums text-text-muted font-medium text-[15px]">
            {doneCount} / {steps.length}
          </span>
        </div>
        <div className="text-sm text-text-dim">{t('remaining', { count: steps.length - doneCount })}</div>
      </div>

      <div className="h-1.5 rounded-full bg-white/[0.07] overflow-hidden">
        <div className="h-full bg-cyan" style={{ width: `${pct}%` }} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {steps.map(s => {
          const isNext = next && s.id === next.id
          if (s.done) {
            return (
              <div key={s.id} className="flex gap-3 items-center bg-win/[0.06] rounded-xl p-4">
                <span className="flex-none w-[26px] h-[26px] rounded-full bg-win text-[#062318] flex items-center justify-center text-sm font-bold">
                  ✓
                </span>
                <span className="text-[15px] text-text-muted">{t(`steps.${s.id}.done`)}</span>
              </div>
            )
          }
          return (
            <div
              key={s.id}
              className={[
                'flex gap-3 items-center justify-between rounded-xl p-3 pl-4',
                isNext ? 'bg-cyan/[0.07] border border-cyan/[0.22]' : 'bg-white/[0.02] border border-white/[0.07]',
              ].join(' ')}
            >
              <span className="text-[15px] font-semibold">{t(`steps.${s.id}.todo`)}</span>
              <Link
                href={s.href}
                className={[
                  'flex-none rounded-lg px-3.5 py-2.5 text-sm font-bold transition',
                  isNext
                    ? 'bg-cyan text-[#001721] hover:brightness-110'
                    : 'border border-white/[0.14] text-text hover:border-white/30',
                ].join(' ')}
              >
                {t(`steps.${s.id}.cta`)}
              </Link>
            </div>
          )
        })}
      </div>
    </div>
  )
}
