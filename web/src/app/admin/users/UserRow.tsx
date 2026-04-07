'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const DEFAULT_BOT_CONFIG = {
  players_primary: 10,
  relax_wait_sec: 60,
  min_hands: 20,
  max_hands: 40,
  dragon_limit: 5,
  require_pb: true,
}

export default function UserRow({ user, billing }: { user: any; billing: any }) {
  const [rate, setRate] = useState(billing?.profit_share_rate ? (billing.profit_share_rate * 100).toString() : '20')
  const [loading, setLoading] = useState(false)
  const [showConfig, setShowConfig] = useState(false)
  const [uploading, setUploading] = useState(false)
  const isActive = billing?.status === 'active'

  async function uploadZip(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    form.append('userId', user.id)
    form.append('version', '1.0.4')
    const res = await fetch('/api/admin/upload', { method: 'POST', body: form })
    if (res.ok) { alert('ZIP送付完了'); router.refresh() }
    else { alert('エラー: ' + (await res.text())) }
    setUploading(false)
    e.target.value = ''
  }
  const cfg = { ...DEFAULT_BOT_CONFIG, ...(billing?.bot_config || {}) }
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
    <>
      <tr className="border-b border-white/5">
        <td className="py-3">
          <div>{user.email}</div>
          {user.is_admin && <span className="text-xs text-accent bg-accent/10 px-1.5 py-0.5 rounded">管理者</span>}
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
              設定
            </button>
          </div>
        </td>
        <td className="py-3">
          {isFree ? (
            <span className="px-2 py-0.5 rounded text-xs bg-accent/20 text-accent">無料</span>
          ) : isSuspended ? (
            <span className="px-2 py-0.5 rounded text-xs bg-banker/20 text-banker">停止中</span>
          ) : billing?.balance > 0 ? (
            <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">有効</span>
          ) : (
            <span className="px-2 py-0.5 rounded text-xs bg-slate-500/20 text-slate-400">ドライラン</span>
          )}
        </td>
        <td className="py-3 font-mono text-xs text-slate-500">{user.referral_code}</td>
        <td className="py-3 text-slate-500">{new Date(user.created_at).toLocaleDateString('ja-JP')}</td>
        <td className="py-3">
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => updateUser(isSuspended ? 'unsuspend' : 'suspend')}
              disabled={loading}
              className={`px-2 py-1 rounded text-xs transition disabled:opacity-50 ${isSuspended ? 'bg-green-500/20 text-green-400' : 'bg-banker/20 text-banker'}`}
            >
              {isSuspended ? '停止解除' : '停止'}
            </button>
            <button
              onClick={() => updateUser(isFree ? 'unfree' : 'set_free')}
              disabled={loading}
              className="px-2 py-1 rounded text-xs bg-accent/20 text-accent hover:bg-accent/30 transition disabled:opacity-50"
            >
              {isFree ? '無料解除' : '無料設定'}
            </button>
            <button
              onClick={() => updateUser(isActive ? 'deactivate' : 'activate')}
              disabled={loading}
              className={`px-2 py-1 rounded text-xs transition disabled:opacity-50 ${isActive ? 'bg-slate-500/20 text-slate-400' : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'}`}
            >
              {isActive ? '無効化' : 'Activate'}
            </button>
            <label className={`px-2 py-1 rounded text-xs cursor-pointer transition ${uploading ? 'opacity-50' : 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30'}`}>
              {uploading ? '送付中...' : 'ZIP送付'}
              <input type="file" accept=".zip" className="hidden" onChange={uploadZip} disabled={uploading} />
            </label>
            <button
              onClick={() => setShowConfig(v => !v)}
              className="px-2 py-1 rounded text-xs bg-white/5 text-slate-400 hover:text-white transition"
            >
              {showConfig ? '▲ 設定' : '▼ 設定'}
            </button>
          </div>
        </td>
      </tr>

      {showConfig && (
        <tr className="border-b border-white/5 bg-white/[0.02]">
          <td colSpan={7} className="py-3 px-4">
            <div className="text-[10px] text-slate-500 mb-2 tracking-widest">TABLE FILTER</div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-0.5 rounded bg-white/5 text-slate-300">PRIMARY ≥ <b>{cfg.players_primary}</b>人</span>
              <span className="px-2 py-0.5 rounded bg-white/5 text-slate-300">RELAX <b>{cfg.relax_wait_sec}</b>秒</span>
              <span className="px-2 py-0.5 rounded bg-white/5 text-slate-300">HANDS <b>{cfg.min_hands}〜{cfg.max_hands}</b></span>
              <span className="px-2 py-0.5 rounded bg-white/5 text-slate-300">DRAGON ≥ <b>{cfg.dragon_limit === 0 ? 'OFF' : cfg.dragon_limit}</b></span>
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${cfg.require_pb ? 'bg-player/20 text-player' : 'bg-white/5 text-slate-500'}`}>
                P{'>'} B: {cfg.require_pb ? 'ON' : 'OFF'}
              </span>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
