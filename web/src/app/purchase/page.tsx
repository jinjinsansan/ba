'use client'

import { useState, useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase-browser'

const PLANS = {
  starter: { name: 'Starter', price: 1000 },
  pro: { name: 'Professional', price: 3000 },
}

export default function PurchasePage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [plan, setPlan] = useState<'starter' | 'pro'>((searchParams.get('plan') as 'starter' | 'pro') || 'starter')
  const [network, setNetwork] = useState<'TRC-20' | 'ERC-20'>('TRC-20')
  const [promoCode, setPromoCode] = useState('')
  const [promoResult, setPromoResult] = useState<{ valid: boolean; message: string; isFree: boolean } | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [orderId, setOrderId] = useState('')

  const selected = PLANS[plan]

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
      setPromoResult({ valid: false, message: 'Invalid promo code', isFree: false })
    } else if (data.used_count >= data.max_uses) {
      setPromoResult({ valid: false, message: 'Promo code expired', isFree: false })
    } else {
      const isFree = data.type === 'package_free'
      setPromoResult({ valid: true, message: isFree ? 'License FREE!' : `${data.discount_percent}% off`, isFree })
    }
  }

  async function handleSubmit() {
    setLoading(true)
    const supabase = createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { router.push('/login'); return }

    const amount = promoResult?.isFree ? 0 : selected.price
    const status = promoResult?.isFree ? 'confirmed' : 'pending'

    const { data, error } = await supabase.from('orders').insert({
      user_id: user.id,
      plan,
      amount,
      promo_code: promoCode.toUpperCase() || null,
      status,
      usdt_network: network,
    }).select().single()

    if (error) {
      alert('Error creating order: ' + error.message)
    } else {
      setOrderId(data.id)
      setSubmitted(true)
      if (promoCode) {
        await supabase.rpc('increment_promo_usage', { code_text: promoCode.toUpperCase() })
      }
    }
    setLoading(false)
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-lg text-center">
          <div className="text-5xl mb-6">{promoResult?.isFree ? '🎉' : '✅'}</div>
          <h1 className="text-3xl font-bold mb-4">
            {promoResult?.isFree ? 'Activated!' : 'Order Submitted'}
          </h1>
          {promoResult?.isFree ? (
            <p className="text-slate-400 mb-8">Your license has been activated. Go to your dashboard to continue.</p>
          ) : (
            <>
              <p className="text-slate-400 mb-4">Send <span className="text-white font-bold">${selected.price} USDT</span> ({network}) to:</p>
              <div className="p-4 rounded-xl bg-bg-card border border-white/10 font-mono text-sm text-player break-all mb-4">
                {network === 'TRC-20' ? (process.env.NEXT_PUBLIC_USDT_TRC20 || 'TRC20 wallet not configured') : (process.env.NEXT_PUBLIC_USDT_ERC20 || 'ERC20 wallet not configured')}
              </div>
              <p className="text-slate-500 text-sm mb-8">Order ID: {orderId}<br />We&apos;ll confirm within 30 minutes after receiving payment.</p>
            </>
          )}
          <button onClick={() => router.push('/dashboard')} className="px-8 py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold">
            Go to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-24 px-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-black text-center mb-2">Purchase License</h1>
        <p className="text-center text-slate-400 mb-12">Select your plan and payment method</p>

        {/* Plan Selection */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          {(Object.entries(PLANS) as [string, { name: string; price: number }][]).map(([key, p]) => (
            <button
              key={key}
              onClick={() => setPlan(key as 'starter' | 'pro')}
              className={`p-6 rounded-xl border text-left transition ${plan === key ? 'border-player bg-player/10' : 'border-white/10 bg-bg-card hover:border-white/20'}`}
            >
              <div className="font-bold text-lg">{p.name}</div>
              <div className="text-2xl font-black mt-1">${p.price.toLocaleString()}</div>
            </button>
          ))}
        </div>

        {/* Network */}
        <div className="mb-8">
          <label className="block text-sm text-slate-400 mb-2">USDT Network</label>
          <div className="grid grid-cols-2 gap-4">
            {(['TRC-20', 'ERC-20'] as const).map(n => (
              <button
                key={n}
                onClick={() => setNetwork(n)}
                className={`p-4 rounded-xl border text-center transition ${network === n ? 'border-player bg-player/10' : 'border-white/10 bg-bg-card hover:border-white/20'}`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        {/* Promo Code */}
        <div className="mb-8">
          <label className="block text-sm text-slate-400 mb-2">Promo Code <span className="text-slate-600">(optional)</span></label>
          <div className="flex gap-3">
            <input
              value={promoCode} onChange={e => setPromoCode(e.target.value)}
              className="flex-1 px-4 py-3 rounded-xl bg-bg-card border border-white/10 text-white focus:outline-none focus:border-player/50 transition"
              placeholder="Enter code"
            />
            <button onClick={checkPromo} className="px-6 py-3 rounded-xl border border-player/30 text-player font-semibold hover:bg-player/10 transition">
              Apply
            </button>
          </div>
          {promoResult && (
            <p className={`text-sm mt-2 ${promoResult.valid ? 'text-green-400' : 'text-banker'}`}>
              {promoResult.message}
            </p>
          )}
        </div>

        {/* Summary */}
        <div className="p-6 rounded-xl bg-bg-card border border-white/10 mb-8">
          <div className="flex justify-between items-center mb-2">
            <span className="text-slate-400">Plan</span>
            <span className="font-bold">{selected.name}</span>
          </div>
          <div className="flex justify-between items-center mb-2">
            <span className="text-slate-400">Network</span>
            <span>{network}</span>
          </div>
          <div className="border-t border-white/10 my-3" />
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Total</span>
            <span className="text-2xl font-black">
              {promoResult?.isFree ? <span className="text-green-400">FREE</span> : `$${selected.price.toLocaleString()}`}
            </span>
          </div>
        </div>

        <button
          onClick={handleSubmit} disabled={loading}
          className="w-full py-4 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold text-lg hover:opacity-90 transition disabled:opacity-50"
        >
          {loading ? 'Processing...' : promoResult?.isFree ? 'Activate License' : 'Submit Order'}
        </button>
      </div>
    </div>
  )
}
