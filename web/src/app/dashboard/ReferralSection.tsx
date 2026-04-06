'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

type Referred = {
  id: string
  email: string
  created_at: string
  total_charged: number
  commission: number
}

export default function ReferralSection({
  referralUrl,
  referred,
  totalEarned,
  totalWithdrawn,
  withdrawals,
}: {
  referralUrl: string
  referred: Referred[]
  totalEarned: number
  totalWithdrawn: number
  withdrawals: any[]
}) {
  const available = totalEarned - totalWithdrawn
  const [copied, setCopied] = useState(false)
  const [showWithdraw, setShowWithdraw] = useState(false)
  const [amount, setAmount] = useState('')
  const [wallet, setWallet] = useState('')
  const [network, setNetwork] = useState('TRC-20')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  function copyUrl() {
    navigator.clipboard.writeText(referralUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function submitWithdraw() {
    setError('')
    const amt = parseFloat(amount)
    if (!amt || amt < 10) return setError('Minimum withdrawal is $10')
    if (!wallet) return setError('Enter wallet address')
    setLoading(true)
    const res = await fetch('/api/referral/withdraw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: amt, wallet_address: wallet, network }),
    })
    const data = await res.json()
    setLoading(false)
    if (!res.ok) return setError(data.error || 'Error')
    setShowWithdraw(false)
    setAmount('')
    setWallet('')
    router.refresh()
  }

  return (
    <div className="p-6 rounded-2xl bg-bg-card border border-white/5 mb-8">
      <h2 className="text-lg font-bold mb-6">Referral Program</h2>

      {/* Referral URL */}
      <div className="mb-6">
        <div className="text-sm text-slate-400 mb-2">Your Referral URL</div>
        <div className="flex gap-2 items-center flex-wrap">
          <code className="flex-1 px-4 py-2.5 rounded-lg bg-bg-primary border border-white/10 text-player font-mono text-sm break-all">
            {referralUrl}
          </code>
          <button
            onClick={copyUrl}
            className="px-4 py-2.5 rounded-lg bg-player/20 text-player text-sm font-semibold hover:bg-player/30 transition flex-shrink-0"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>

      {/* Commission Balance */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-4 rounded-xl bg-bg-primary border border-white/5">
          <div className="text-xs text-slate-500 mb-1">Total Earned</div>
          <div className="text-xl font-black text-green-400">${totalEarned.toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl bg-bg-primary border border-white/5">
          <div className="text-xs text-slate-500 mb-1">Withdrawn</div>
          <div className="text-xl font-black text-slate-400">${totalWithdrawn.toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl bg-bg-primary border border-white/5">
          <div className="text-xs text-slate-500 mb-1">Available</div>
          <div className="text-xl font-black text-player">${available.toFixed(2)}</div>
        </div>
      </div>

      {/* Referred Users */}
      {referred.length > 0 && (
        <div className="mb-6">
          <div className="text-sm text-slate-400 mb-3">Referred Users ({referred.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-500 text-left border-b border-white/5">
                  <th className="pb-2">Email</th>
                  <th className="pb-2">Joined</th>
                  <th className="pb-2">Total Charged</th>
                  <th className="pb-2">Your Commission (5%)</th>
                </tr>
              </thead>
              <tbody>
                {referred.map(r => (
                  <tr key={r.id} className="border-b border-white/[0.03]">
                    <td className="py-2 text-white">{r.email}</td>
                    <td className="py-2 text-slate-500">{new Date(r.created_at).toLocaleDateString()}</td>
                    <td className="py-2 font-bold">${r.total_charged.toFixed(2)}</td>
                    <td className="py-2 text-green-400 font-bold">+${r.commission.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Withdrawal Requests */}
      {withdrawals.length > 0 && (
        <div className="mb-6">
          <div className="text-sm text-slate-400 mb-3">Withdrawal History</div>
          <div className="space-y-2">
            {withdrawals.map((w: any) => (
              <div key={w.id} className="flex items-center justify-between p-3 rounded-lg bg-bg-primary border border-white/5 text-sm">
                <div>
                  <span className="font-bold">${Number(w.amount).toFixed(2)}</span>
                  <span className="text-slate-500 ml-2">{w.network}</span>
                  <span className="text-slate-600 ml-2 text-xs">{new Date(w.created_at).toLocaleDateString()}</span>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  w.status === 'approved' ? 'bg-green-500/20 text-green-400' :
                  w.status === 'rejected' ? 'bg-banker/20 text-banker' :
                  'bg-yellow-500/20 text-yellow-400'
                }`}>
                  {w.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Withdraw Button */}
      {available >= 10 && !showWithdraw && (
        <button
          onClick={() => setShowWithdraw(true)}
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold text-sm hover:opacity-90 transition"
        >
          Request Withdrawal
        </button>
      )}

      {showWithdraw && (
        <div className="p-5 rounded-xl bg-bg-primary border border-white/10 space-y-4">
          <div className="text-sm font-bold mb-2">Withdrawal Request</div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Amount (USD) — Available: ${available.toFixed(2)}</label>
            <input
              type="number" value={amount} onChange={e => setAmount(e.target.value)}
              placeholder="10.00" min="10" max={available}
              className="w-full px-3 py-2 rounded-lg bg-bg-card border border-white/10 text-white text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Network</label>
            <div className="flex gap-2">
              {['TRC-20', 'ERC-20'].map(n => (
                <button key={n} onClick={() => setNetwork(n)}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${network === n ? 'bg-player text-white' : 'bg-bg-card text-slate-400 border border-white/10'}`}>
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">USDT Wallet Address</label>
            <input
              type="text" value={wallet} onChange={e => setWallet(e.target.value)}
              placeholder="T... or 0x..."
              className="w-full px-3 py-2 rounded-lg bg-bg-card border border-white/10 text-white text-sm font-mono"
            />
          </div>
          {error && <p className="text-banker text-xs">{error}</p>}
          <div className="flex gap-3">
            <button onClick={submitWithdraw} disabled={loading}
              className="px-5 py-2.5 rounded-lg bg-player text-white text-sm font-bold hover:bg-player/90 transition disabled:opacity-50">
              {loading ? 'Submitting...' : 'Submit'}
            </button>
            <button onClick={() => { setShowWithdraw(false); setError('') }}
              className="px-5 py-2.5 rounded-lg bg-white/5 text-slate-400 text-sm hover:text-white transition">
              Cancel
            </button>
          </div>
        </div>
      )}

      {available < 10 && available > 0 && (
        <p className="text-xs text-slate-600 mt-2">Minimum withdrawal is $10. Keep earning to reach the threshold.</p>
      )}
    </div>
  )
}
