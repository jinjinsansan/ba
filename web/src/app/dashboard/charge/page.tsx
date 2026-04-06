'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase-browser'

export default function ChargePage() {
  const [amount, setAmount] = useState('')
  const [network, setNetwork] = useState<'TRC-20' | 'ERC-20'>('TRC-20')
  const [promoCode, setPromoCode] = useState('')
  const [promoMessage, setPromoMessage] = useState('')
  const [promoValid, setPromoValid] = useState(false)
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [finalAmount, setFinalAmount] = useState(0)
  const [isFree, setIsFree] = useState(false)
  const router = useRouter()

  async function checkPromo() {
    if (!promoCode.trim()) return
    const supabase = createClient()
    const { data } = await supabase
      .from('promo_codes')
      .select('*')
      .eq('code', promoCode.toUpperCase())
      .eq('active', true)
      .single()

    if (!data) {
      setPromoMessage('Invalid promo code')
      setPromoValid(false)
    } else if (data.used_count >= data.max_uses) {
      setPromoMessage('Code expired')
      setPromoValid(false)
    } else if (data.type === 'charge_free') {
      setPromoMessage('Charge FREE!')
      setPromoValid(true)
    } else if (data.type === 'discount') {
      setPromoMessage(`${data.discount_percent}% off`)
      setPromoValid(true)
    } else {
      setPromoMessage('Code applied')
      setPromoValid(true)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    const res = await fetch('/api/charge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: amount || '0', promoCode: promoCode.trim() || null, network }),
    })
    const data = await res.json()
    if (res.ok) {
      setFinalAmount(data.amount)
      setIsFree(data.isFree)
      setSubmitted(true)
    } else {
      alert('Error: ' + (data.error || 'Unknown error'))
    }
    setLoading(false)
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-lg text-center">
          <div className="text-5xl mb-6">{isFree ? '🎉' : '✅'}</div>
          <h1 className="text-3xl font-bold mb-4">{isFree ? 'Charge Activated!' : 'Charge Submitted'}</h1>
          {isFree ? (
            <p className="text-slate-400 mb-8">Your account is now active with unlimited balance.</p>
          ) : (
            <>
              <p className="text-slate-400 mb-4">Send <span className="text-white font-bold">${finalAmount} USDT</span> ({network}) to:</p>
              <div className="p-4 rounded-xl bg-bg-card border border-white/10 font-mono text-sm text-player break-all mb-4">
                {network === 'TRC-20' ? (process.env.NEXT_PUBLIC_USDT_TRC20 || 'TRC20 wallet not configured') : (process.env.NEXT_PUBLIC_USDT_ERC20 || 'ERC20 wallet not configured')}
              </div>
              <p className="text-slate-500 text-sm mb-8">Your balance will be updated once we confirm the payment.</p>
            </>
          )}
          <button onClick={() => router.push('/dashboard')} className="px-8 py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold">
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-24 px-6">
      <div className="max-w-lg mx-auto">
        <h1 className="text-3xl font-black text-center mb-2">Charge Balance</h1>
        <p className="text-center text-slate-400 mb-12">Add funds to enable live betting</p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm text-slate-400 mb-2">Amount (USD)</label>
            <input type="number" min="100" step="100" value={amount}
              onChange={e => setAmount(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition"
              placeholder="Minimum $100" />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">USDT Network</label>
            <div className="grid grid-cols-2 gap-4">
              {(['TRC-20', 'ERC-20'] as const).map(n => (
                <button key={n} type="button" onClick={() => setNetwork(n)}
                  className={`p-3 rounded-xl border text-center transition ${network === n ? 'border-player bg-player/10' : 'border-white/10 bg-bg-card hover:border-white/20'}`}>
                  {n}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Promo Code <span className="text-slate-600">(optional)</span></label>
            <div className="flex gap-3">
              <input value={promoCode} onChange={e => setPromoCode(e.target.value)}
                className="flex-1 px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition"
                placeholder="Enter code" />
              <button type="button" onClick={checkPromo} className="px-6 py-3 rounded-xl border border-player/30 text-player font-semibold hover:bg-player/10 transition">Apply</button>
            </div>
            {promoMessage && <p className={`text-sm mt-2 ${promoValid ? 'text-green-400' : 'text-banker'}`}>{promoMessage}</p>}
          </div>

          <button type="submit" disabled={loading}
            className="w-full py-4 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold text-lg hover:opacity-90 transition disabled:opacity-50">
            {loading ? 'Processing...' : 'Submit Charge'}
          </button>
        </form>
      </div>
    </div>
  )
}
