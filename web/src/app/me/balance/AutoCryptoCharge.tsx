'use client'

import { useEffect, useState } from 'react'

// USDT(TRC-20)自動チャージ。POST /api/payments/create でユニーク端数つき金額を発行し、
// その正確な額を受取アドレスへ送ってもらう → VPSポーラーが着金照合して自動反映。
type Order = {
  order_id: string
  kind: 'license' | 'charge'
  amount: number
  token: string
  network: string
  address: string
  expires_at: string
}

export default function AutoCryptoCharge() {
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [order, setOrder] = useState<Order | null>(null)
  const [remain, setRemain] = useState('')
  const [copied, setCopied] = useState('')

  async function create(kind: 'license' | 'charge') {
    setErr(''); setLoading(true); setOrder(null)
    try {
      const body = kind === 'license' ? { kind } : { kind, amount: parseInt(amount, 10) }
      const res = await fetch('/api/payments/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) { setErr(data.error || '作成に失敗しました'); return }
      setOrder(data as Order)
    } catch (e: any) {
      setErr(e?.message || 'ネットワークエラー')
    } finally { setLoading(false) }
  }

  useEffect(() => {
    if (!order) return
    const t = setInterval(() => {
      const ms = new Date(order.expires_at).getTime() - Date.now()
      if (ms <= 0) { setRemain('期限切れ'); return }
      const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000)
      setRemain(`${m}分${s.toString().padStart(2, '0')}秒`)
    }, 1000)
    return () => clearInterval(t)
  }, [order])

  const qr = order
    ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(order.address)}`
    : ''

  return (
    <div className="rounded-xl border border-cyan/20 bg-cyan/[0.03] p-5">
      <div className="text-sm font-semibold text-cyan mb-1">暗号資産で自動チャージ (USDT / TRC-20)</div>
      <div className="text-xs text-text-muted mb-4 leading-relaxed">
        金額を入れて注文を作成 → 表示された<strong>正確な金額(端数まで)</strong>を送金 → 着金後 約1〜2分で自動反映されます。
      </div>

      {!order && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="number" min="1" step="1" inputMode="numeric" placeholder="チャージ額 (USD)"
              value={amount} onChange={e => setAmount(e.target.value)}
              className="flex-1 px-3 py-2 rounded bg-white/[0.03] border border-white/10 text-white text-sm"
            />
            <button onClick={() => create('charge')} disabled={loading || !(parseInt(amount, 10) > 0)}
              className="px-4 py-2 rounded text-sm bg-cyan/20 text-cyan hover:bg-cyan/30 transition disabled:opacity-40">
              {loading ? '作成中…' : 'チャージ注文'}
            </button>
          </div>
          <button onClick={() => create('license')} disabled={loading}
            className="w-full px-4 py-2 rounded text-sm bg-yellow-500/15 text-yellow-300 hover:bg-yellow-500/25 transition disabled:opacity-40">
            ライセンス購入 ($2000)
          </button>
          {err && <div className="text-xs text-red-400">{err}</div>}
        </div>
      )}

      {order && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted">{order.kind === 'license' ? 'ライセンス' : 'チャージ'}注文</span>
            <span className="text-text-dim">期限まで {remain}</span>
          </div>
          <div className="rounded-lg bg-black/30 border border-white/10 p-3">
            <div className="text-[11px] text-text-muted">この正確な金額を送金 (端数まで一致が必須)</div>
            <div className="flex items-center gap-2">
              <div className="text-2xl font-bold text-cyan font-mono">{order.amount.toFixed(2)} USDT</div>
              <button onClick={() => { navigator.clipboard?.writeText(order.amount.toFixed(2)); setCopied('amount'); setTimeout(() => setCopied(''), 1500) }}
                className="px-2 py-1 rounded text-[11px] bg-cyan/20 text-cyan hover:bg-cyan/30 transition">
                {copied === 'amount' ? 'コピー済' : '金額をコピー'}
              </button>
            </div>
            <div className="mt-1 text-[11px] text-text-dim">ネットワーク: {order.network}</div>
          </div>
          <div className="flex gap-3 items-center">
            {qr && <img src={qr} alt="address QR" width={120} height={120} className="rounded bg-white p-1" />}
            <div className="min-w-0">
              <div className="text-[11px] text-text-muted mb-1">送金先アドレス</div>
              <div className="font-mono text-xs break-all text-text">{order.address}</div>
              <button onClick={() => { navigator.clipboard?.writeText(order.address); setCopied('address'); setTimeout(() => setCopied(''), 1500) }}
                className="mt-2 px-2 py-1 rounded text-[11px] bg-white/10 text-text-muted hover:text-white transition">
                {copied === 'address' ? 'コピー済' : 'アドレスをコピー'}
              </button>
            </div>
          </div>
          <div className="text-[11px] text-amber-400/90 leading-relaxed">
            ⚠️ 必ず <b>{order.amount.toFixed(2)} USDT ちょうど</b> を送ってください(端数で本人確認します)。
            少額違いだと自動反映されません。反映後は自動で稼働可能になります。
          </div>
          <button onClick={() => { setOrder(null); setAmount('') }}
            className="text-xs text-text-dim hover:text-text underline">別の金額で作り直す</button>
        </div>
      )}
    </div>
  )
}
