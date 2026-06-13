'use client'

import AutoCryptoCharge from '@/app/me/balance/AutoCryptoCharge'

// チャージは自動暗号決済に一本化(2026-06-14)。手動申請+管理承認フローは廃止し、
// USDT(TRC-20)金額照合の自動反映に統合。
export default function ChargePage() {
  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <div className="mb-4">
        <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">Charge</div>
        <h1 className="text-2xl font-bold text-text mt-1">資金チャージ</h1>
        <p className="text-sm text-text-muted mt-1">
          USDT(TRC-20)で自動チャージ。金額を入れて注文 → 表示された<strong>正確な金額</strong>を送金すると、約1〜2分で<strong>自動反映</strong>されます(手動承認は不要)。
        </p>
      </div>
      <AutoCryptoCharge mode="charge" />
    </div>
  )
}
