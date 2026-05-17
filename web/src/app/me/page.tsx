import { createClient } from '@/lib/supabase-server'
import Link from 'next/link'

export default async function MePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const [{ data: profile }, { data: billing }, { data: latestOrder }, { data: latestDeliverable }, { data: lastDeduction }] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('orders').select('*').eq('user_id', user.id).order('created_at', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('deliverables').select('*').eq('user_id', user.id).order('created_at', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(1).maybeSingle(),
  ])

  const hasActiveCharge = billing && billing.balance > 0 && !billing.suspended
  let statusLabel = 'No License'
  let statusColor = 'text-text-muted'
  let statusBg = 'bg-bg-card border-white/10'
  // is_free = 管理者から課金免除されているユーザ。ライセンス購入もチャージも不要で常に ACTIVE 扱い。
  if (billing?.is_free && !billing?.suspended) {
    statusLabel = 'ACTIVE — 課金免除プラン (Live Betting Enabled)'
    statusColor = 'text-green-400'
    statusBg = 'bg-green-500/10 border-green-500/30'
  } else if (!latestOrder) { statusLabel = 'No License — Purchase to start'; statusColor = 'text-text-muted' }
  else if (latestOrder.status === 'pending' || latestOrder.status === 'sent') { statusLabel = 'PENDING — Awaiting payment'; statusColor = 'text-yellow-400'; statusBg = 'bg-yellow-500/10 border-yellow-500/30' }
  else if (billing?.suspended) { statusLabel = 'SUSPENDED — Contact support'; statusColor = 'text-banker'; statusBg = 'bg-banker/10 border-banker/30' }
  else if (!hasActiveCharge) { statusLabel = 'DRY RUN — Charge to enable live bets'; statusColor = 'text-player'; statusBg = 'bg-player/10 border-player/30' }
  else { statusLabel = 'ACTIVE — Live Betting Enabled'; statusColor = 'text-green-400'; statusBg = 'bg-green-500/10 border-green-500/30' }

  const balanceCardDesc = billing?.is_free
    ? '課金免除プラン適用中 (チャージ不要)'
    : `現在 $${Number(billing?.balance || 0).toFixed(2)} / 追加チャージはこちら`
  const cards: Array<{ href: string; title: string; desc: string; cta: string; tone: 'accent' | 'warn' | 'ok' | 'muted' }> = [
    { href: '/me/realtime', title: 'ライブ運用状況', desc: '受け子のリアルタイム PnL・残高・BET 件数を 30 秒更新', cta: '見る', tone: 'accent' },
    { href: '/me/balance', title: '残高・チャージ', desc: balanceCardDesc, cta: '管理', tone: billing?.is_free ? 'ok' : (hasActiveCharge ? 'ok' : 'warn') },
    { href: '/me/settlements', title: '日次精算履歴', desc: lastDeduction ? `最終: ${lastDeduction.date} / PnL ${Number(lastDeduction.daily_profit || 0) >= 0 ? '+' : ''}$${Number(lastDeduction.daily_profit || 0).toFixed(2)}` : '履歴なし', cta: '一覧', tone: 'accent' },
    { href: '/me/telegram', title: 'Telegram 連携', desc: '日次精算・未払い通知を Telegram で受け取り', cta: '設定', tone: 'muted' },
    { href: '/me/referral', title: '紹介プログラム', desc: '紹介 URL の共有 / 報酬の引出', cta: '開く', tone: 'muted' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">II · Member Console</div>
        <h1 className="text-2xl sm:text-3xl font-hud">マイページ</h1>
        <p className="text-text-muted text-sm mt-2 break-all">{profile?.email || user.email}</p>
      </div>

      {/* Status Banner */}
      <div className={`p-5 rounded-2xl border glass-soft ${statusBg}`}>
        <div className="text-xs text-text-muted mb-1">Account Status</div>
        <div className={`text-lg sm:text-xl font-bold ${statusColor}`}>{statusLabel}</div>
        {billing?.is_free ? (
          <button
            type="button"
            disabled
            className="inline-block px-5 py-2 mt-3 text-sm rounded-lg bg-bg-glass text-text-dim border border-accent/10 cursor-not-allowed opacity-60"
            title="管理者から課金免除を受けているため購入不要です"
          >
            ライセンス購入 (免除済)
          </button>
        ) : !latestOrder ? (
          <Link href="/purchase" className="btn-primary inline-block px-5 py-2 mt-3 text-sm">ライセンス購入</Link>
        ) : !hasActiveCharge ? (
          <Link href="/me/balance" className="btn-primary inline-block px-5 py-2 mt-3 text-sm">残高をチャージ</Link>
        ) : null}
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] text-text-dim tracking-widest uppercase">Balance</div>
          {billing?.is_free ? (
            <div className="text-base sm:text-lg font-bold text-accent mt-1">課金免除</div>
          ) : (
            <div className="text-lg sm:text-xl font-bold text-text mt-1">${Number(billing?.balance || 0).toFixed(2)}</div>
          )}
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] text-text-dim tracking-widest uppercase">Profit Share</div>
          <div className="text-lg sm:text-xl font-bold text-text mt-1">
            {billing ? `${(Number(billing.profit_share_rate) * 100).toFixed(0)}%` : '—'}
          </div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] text-text-dim tracking-widest uppercase">Carry Loss</div>
          <div className="text-lg sm:text-xl font-bold text-banker mt-1">
            ${Number(billing?.carry_loss || 0).toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] text-text-dim tracking-widest uppercase">Total Charged</div>
          <div className="text-lg sm:text-xl font-bold text-text mt-1">
            ${Number(billing?.total_charged || 0).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Quick navigation cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map(c => (
          <Link
            key={c.href}
            href={c.href}
            className="p-5 rounded-2xl glass-card hover:border-accent/40 transition group"
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-base font-bold text-text">{c.title}</h3>
              <span className="text-xs text-text-muted group-hover:text-accent transition">→</span>
            </div>
            <p className="text-xs text-text-muted leading-relaxed">{c.desc}</p>
            <div className="mt-3 text-[10px] tracking-widest uppercase text-accent">{c.cta}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
