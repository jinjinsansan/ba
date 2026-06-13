'use client'

import AutoCryptoCharge from '@/app/me/balance/AutoCryptoCharge'

// ライセンス購入も自動暗号決済に一本化(2026-06-14)。手動送金+管理承認は廃止し、
// USDT(TRC-20)金額照合で bot_paid を自動有効化。
export default function PurchasePage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-4">
          <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">License</div>
          <h1 className="text-2xl font-bold text-text mt-1">ライセンス購入</h1>
          <p className="text-sm text-text-muted mt-1">
            ライセンス料 <strong>$2000</strong>(USDT TRC-20)。下のボタンで注文 → 表示された<strong>正確な金額</strong>を送金すると、約1〜2分で<strong>自動的にライセンス有効化</strong>されます(手動承認は不要)。
          </p>
        </div>
        <AutoCryptoCharge mode="license" />
      </div>
    </div>
  )
}
