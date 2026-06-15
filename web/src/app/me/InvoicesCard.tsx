'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardHead } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Money } from '@/components/ui/Money'

type Invoice = { id: string; amount: number; memo?: string | null; created_at?: string }

// ダッシュボードの「未払い請求書」カード。クリックで決済(ハイブリッド):
// 残高で賄えれば即支払い、不足なら残高・チャージ画面(USDT自動チャージ)へ誘導。
export default function InvoicesCard({ invoices }: { invoices: Invoice[] }) {
  const router = useRouter()
  const [busyId, setBusyId] = useState<string | null>(null)
  const [msg, setMsg] = useState<string>('')

  async function pay(inv: Invoice) {
    setBusyId(inv.id); setMsg('')
    try {
      const res = await fetch(`/api/invoices/${inv.id}/pay`, { method: 'POST' })
      const j = await res.json().catch(() => ({}))
      if (!res.ok) { setMsg(j.error || '決済に失敗しました'); return }
      if (j.paid) {
        setMsg('支払いが完了しました。')
        router.refresh()
      } else if (j.needCharge) {
        setMsg(`残高が不足しています(不足 $${Number(j.shortfall).toFixed(2)})。チャージ画面へ移動します…`)
        setTimeout(() => router.push('/me/balance'), 900)
      } else if (j.already) {
        setMsg('この請求書は既に処理済みです。')
        router.refresh()
      }
    } catch {
      setMsg('通信エラーが発生しました。')
    } finally {
      setBusyId(null)
    }
  }

  if (!invoices.length) return null
  const total = invoices.reduce((s, i) => s + Number(i.amount || 0), 0)

  return (
    <Card padded={false} className="mb-4 border-warn/30 bg-warn/[0.03]">
      <CardHead right={<span className="text-warn font-semibold text-sm">未払い ${total.toFixed(2)}</span>}>
        請求書 · お支払い
      </CardHead>
      <div className="divide-y divide-white/[0.06]">
        {invoices.map(inv => (
          <div key={inv.id} className="flex items-center justify-between gap-3 px-5 py-4">
            <div className="min-w-0">
              <div className="text-base font-semibold"><Money value={Number(inv.amount)} size="xl" weight="bold" /></div>
              {inv.memo ? <div className="text-xs text-text-muted mt-0.5 break-words">{inv.memo}</div> : null}
              {inv.created_at ? <div className="text-[10px] text-text-dim mt-0.5 font-mono">{new Date(inv.created_at).toLocaleDateString('ja-JP')}</div> : null}
            </div>
            <Button tone="primary" size="sm" disabled={busyId === inv.id} onClick={() => pay(inv)}>
              {busyId === inv.id ? '処理中…' : '支払う'}
            </Button>
          </div>
        ))}
      </div>
      {msg ? <div className="px-5 py-3 text-xs text-text-muted border-t border-white/[0.06]">{msg}</div> : null}
    </Card>
  )
}
