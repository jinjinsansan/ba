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
  const [cfg, setCfg] = useState<any>({ ...DEFAULT_BOT_CONFIG, ...(billing?.bot_config || {}) })
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
          <td colSpan={7} className="py-4 px-4">
            <div className="text-xs text-slate-400 mb-3 font-semibold tracking-widest">BOT TABLE FILTER CONFIG</div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                { key: 'players_primary', label: 'PRIMARY PLAYERS', min: 1, max: 50 },
                { key: 'relax_wait_sec',  label: 'RELAX (SEC)',      min: 10, max: 300 },
                { key: 'min_hands',       label: 'MIN HANDS',        min: 5,  max: 40 },
                { key: 'max_hands',       label: 'MAX HANDS',        min: 20, max: 80 },
                { key: 'dragon_limit',    label: 'DRAGON LIMIT',     min: 0,  max: 10 },
              ].map(({ key, label, min, max }) => (
                <div key={key}>
                  <div className="text-slate-500 text-[10px] mb-1 tracking-wider">{label}</div>
                  <input
                    type="number" min={min} max={max} value={cfg[key] ?? DEFAULT_BOT_CONFIG[key as keyof typeof DEFAULT_BOT_CONFIG]}
                    onChange={e => setCfg((p: any) => ({ ...p, [key]: parseInt(e.target.value) }))}
                    className="w-full px-2 py-1 rounded bg-bg-primary border border-white/10 text-white text-sm"
                  />
                </div>
              ))}

              <div>
                <div className="text-slate-500 text-[10px] mb-1 tracking-wider">P {'>'} B REQUIRED</div>
                <button
                  onClick={() => setCfg((p: any) => ({ ...p, require_pb: !p.require_pb }))}
                  className={`px-3 py-1 rounded text-xs font-bold transition ${cfg.require_pb ? 'bg-player/20 text-player' : 'bg-white/5 text-slate-500'}`}
                >
                  {cfg.require_pb ? 'ON' : 'OFF'}
                </button>
              </div>
            </div>

            <div className="mt-4 flex gap-2">
              <button
                onClick={async () => {
                  await updateUser('set_bot_config', cfg)
                  setShowConfig(false)
                }}
                disabled={loading}
                className="px-3 py-1.5 rounded text-xs bg-player/20 text-player hover:bg-player/30 transition disabled:opacity-50"
              >
                保存
              </button>
              <button
                onClick={() => setCfg({ ...DEFAULT_BOT_CONFIG })}
                className="px-3 py-1.5 rounded text-xs bg-white/5 text-slate-400 hover:text-white transition"
              >
                デフォルトに戻す
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
