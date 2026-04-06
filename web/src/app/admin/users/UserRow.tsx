'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function UserRow({ user, billing }: { user: any; billing: any }) {
  const [rate, setRate] = useState(billing?.profit_share_rate ? (billing.profit_share_rate * 100).toString() : '20')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function updateUser(action: string, value?: any) {
    setLoading(true)
    const res = await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: user.id, action, value }),
    })
    if (res.ok) router.refresh()
    else alert('Error: ' + (await res.text()))
    setLoading(false)
  }

  const isSuspended = billing?.suspended
  const isFree = billing?.is_free

  return (
    <tr className="border-b border-white/5">
      <td className="py-3">
        <div>{user.email}</div>
        {user.is_admin && <span className="text-xs text-accent bg-accent/10 px-1.5 py-0.5 rounded">admin</span>}
      </td>
      <td className="py-3 font-bold">${billing?.balance?.toFixed(2) || '0.00'}</td>
      <td className="py-3">
        <div className="flex items-center gap-2">
          <input
            type="number" min="0" max="100" value={rate}
            onChange={e => setRate(e.target.value)}
            className="w-16 px-2 py-1 rounded bg-bg-primary border border-white/10 text-white text-sm"
          />
          <span className="text-slate-500">%</span>
          <button
            onClick={() => updateUser('set_rate', parseFloat(rate) / 100)}
            disabled={loading}
            className="px-2 py-1 rounded text-xs bg-player/20 text-player hover:bg-player/30 transition disabled:opacity-50"
          >
            Set
          </button>
        </div>
      </td>
      <td className="py-3">
        {isFree ? (
          <span className="px-2 py-0.5 rounded text-xs bg-accent/20 text-accent">FREE</span>
        ) : isSuspended ? (
          <span className="px-2 py-0.5 rounded text-xs bg-banker/20 text-banker">SUSPENDED</span>
        ) : billing?.balance > 0 ? (
          <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">ACTIVE</span>
        ) : (
          <span className="px-2 py-0.5 rounded text-xs bg-slate-500/20 text-slate-400">DRY RUN</span>
        )}
      </td>
      <td className="py-3 font-mono text-xs text-slate-500">{user.referral_code}</td>
      <td className="py-3 text-slate-500">{new Date(user.created_at).toLocaleDateString()}</td>
      <td className="py-3">
        <div className="flex gap-2">
          <button
            onClick={() => updateUser(isSuspended ? 'unsuspend' : 'suspend')}
            disabled={loading}
            className={`px-2 py-1 rounded text-xs transition disabled:opacity-50 ${isSuspended ? 'bg-green-500/20 text-green-400' : 'bg-banker/20 text-banker'}`}
          >
            {isSuspended ? 'Unsuspend' : 'Suspend'}
          </button>
          <button
            onClick={() => updateUser(isFree ? 'unfree' : 'set_free')}
            disabled={loading}
            className="px-2 py-1 rounded text-xs bg-accent/20 text-accent hover:bg-accent/30 transition disabled:opacity-50"
          >
            {isFree ? 'Remove Free' : 'Set Free'}
          </button>
        </div>
      </td>
    </tr>
  )
}
