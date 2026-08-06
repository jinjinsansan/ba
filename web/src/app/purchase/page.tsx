'use client'

// app/purchase/page.tsx — サブスクの更新(リデザイン 2026-08)
// 新料金モデル: $200 / 30日(登録日起算)。期限が近い場合は警告カードを最上部に(説明書3.6)。
//
// TODO: wire real data — サブスク$200の注文APIは未実装。下の AutoCryptoCharge は
// 旧ライセンス($2000)モードのまま動いている。バックエンド(subscriptions +
// payments/create の kind='subscription')実装までこのページを本番反映しないこと。
// 期限・日数もモック値。

import { useTranslations } from 'next-intl'
import AutoCryptoCharge from '@/app/me/balance/AutoCryptoCharge'

export default function PurchasePage() {
  const t = useTranslations('purchaseV2')

  // TODO: wire real data — モックの期限情報
  const mock = {
    daysLeft: 3,
    expiresOn: '2026-08-09',
    periodFrom: '8月9日',
    periodTo: '9月8日',
  }
  const nearExpiry = mock.daysLeft <= 7

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md flex flex-col gap-4">
        <div>
          <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">{t('kicker')}</div>
          <h1 className="text-2xl font-bold text-text mt-1">{t('title')}</h1>
        </div>

        {nearExpiry && (
          <div className="bg-surface border border-warn/25 rounded-2xl p-5 flex flex-col gap-2">
            <div className="text-sm text-warn font-semibold">{t('warnTitle', { days: mock.daysLeft })}</div>
            <div className="text-[15px] leading-[1.8] text-text-muted">
              {t('warnBody', { date: mock.expiresOn })}
            </div>
          </div>
        )}

        <div className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col gap-4">
          <div className="flex justify-between items-baseline">
            <span className="text-[15px] text-text-muted">{t('amount')}</span>
            <span className="font-mono tabular-nums text-[34px] font-bold">$200</span>
          </div>
          <div className="h-px bg-white/[0.07]" />
          <div className="flex justify-between text-[15px]">
            <span className="text-text-muted">{t('currency')}</span>
            <span>{t('currencyValue')}</span>
          </div>
          <div className="flex justify-between text-[15px]">
            <span className="text-text-muted">{t('period')}</span>
            <span className="font-mono tabular-nums">{mock.periodFrom} → {mock.periodTo}</span>
          </div>
        </div>

        <AutoCryptoCharge mode="license" />

        <p className="text-[13px] leading-[1.85] text-text-dim text-center m-0">{t('note')}</p>
      </div>
    </div>
  )
}
