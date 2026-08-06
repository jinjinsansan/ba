// app/purchase/page.tsx — サブスクの更新(2026-08 新料金モデル・実データ)
// billing.expires_at から期限・更新後の有効期間を計算して表示。
// 決済は AutoCryptoCharge の subscription モード($200・金額マッチング自動有効化)。

import { redirect } from 'next/navigation'
import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import AutoCryptoCharge from '@/app/me/balance/AutoCryptoCharge'

export default async function PurchasePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const t = await getTranslations('purchaseV2')

  const { data: billing } = await supabase.from('billing')
    .select('expires_at, is_free')
    .eq('user_id', user.id)
    .maybeSingle()

  const now = Date.now()
  const expTs = billing?.expires_at ? new Date(String(billing.expires_at)).getTime() : null
  const daysLeft = expTs != null ? Math.ceil((expTs - now) / 86_400_000) : null
  const nearExpiry = daysLeft != null && daysLeft <= 7

  // 更新後の有効期間: max(now, 現期限) から +30日(payments/credit と同じ計算)
  const baseTs = Math.max(now, expTs ?? 0)
  const fmt = (ts: number) => new Date(ts).toLocaleDateString('ja-JP', { timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric' })
  const periodFrom = fmt(baseTs)
  const periodTo = fmt(baseTs + 30 * 86_400_000)

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md flex flex-col gap-4">
        <div>
          <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">{t('kicker')}</div>
          <h1 className="text-2xl font-bold text-text mt-1">{t('title')}</h1>
        </div>

        {nearExpiry && daysLeft != null && (
          <div className="bg-surface border border-warn/25 rounded-2xl p-5 flex flex-col gap-2">
            <div className="text-sm text-warn font-semibold">{t('warnTitle', { days: Math.max(0, daysLeft) })}</div>
            <div className="text-[15px] leading-[1.8] text-text-muted">
              {t('warnBody', { date: expTs != null ? fmt(expTs) : '' })}
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
            <span className="font-mono tabular-nums">{periodFrom} → {periodTo}</span>
          </div>
        </div>

        <AutoCryptoCharge mode="subscription" />

        <p className="text-[13px] leading-[1.85] text-text-dim text-center m-0">{t('note')}</p>
      </div>
    </div>
  )
}
