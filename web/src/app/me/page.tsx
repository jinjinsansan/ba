import Link from 'next/link'
import { createClient } from '@/lib/supabase-server'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader, Label } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'
import { Dot } from '@/components/ui/Dot'
import { Button } from '@/components/ui/Button'

export default async function MePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const [
    { data: profile },
    { data: billing },
    { data: latestOrder },
    { data: lastDeduction },
  ] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('orders').select('*').eq('user_id', user.id).order('created_at', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(1).maybeSingle(),
  ])

  const hasActiveCharge = billing && billing.balance > 0 && !billing.suspended

  type StatusTone = 'live' | 'warn' | 'danger' | 'info'
  let statusLabel = 'No License — Purchase to start'
  let statusTone: StatusTone = 'info'

  if (billing?.is_free && !billing?.suspended) {
    statusLabel = '課金免除プラン — Live Betting Enabled'
    statusTone = 'live'
  } else if (!latestOrder) {
    statusLabel = 'No License — Purchase to start'
    statusTone = 'info'
  } else if (latestOrder.status === 'pending' || latestOrder.status === 'sent') {
    statusLabel = 'PENDING — Awaiting payment'
    statusTone = 'warn'
  } else if (billing?.suspended) {
    statusLabel = 'SUSPENDED — Contact support'
    statusTone = 'danger'
  } else if (!hasActiveCharge) {
    statusLabel = 'DRY RUN — Charge to enable live bets'
    statusTone = 'warn'
  } else {
    statusLabel = 'ACTIVE — Live Betting Enabled'
    statusTone = 'live'
  }

  return (
    <div>
      <PageHeader
        kicker="Member · Home"
        title="マイページ"
        sub={profile?.email || user.email || undefined}
        right={
          billing?.is_free
            ? <Pill tone="free">課金免除プラン</Pill>
            : statusTone === 'live'
              ? <Pill tone="live" dot>LIVE 稼働中</Pill>
              : <Pill tone={statusTone}>{statusLabel.split(' —')[0]}</Pill>
        }
      />

      {/* Status banner */}
      <div
        className={[
          'flex items-center gap-3 p-4 rounded-lg border mb-4',
          statusTone === 'live'   && 'bg-win/5 border-win/20',
          statusTone === 'warn'   && 'bg-warn/5 border-warn/22',
          statusTone === 'danger' && 'bg-lose/5 border-lose/22',
          statusTone === 'info'   && 'bg-cyan/5 border-cyan/22',
        ].filter(Boolean).join(' ')}
      >
        <Dot tone={statusTone === 'live' ? 'win' : statusTone === 'warn' ? 'warn' : statusTone === 'danger' ? 'lose' : 'cyan'} pulse={statusTone === 'live'} />
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[10px] text-text-muted tracking-[0.15em] uppercase">Account Status</div>
          <div className="text-[15px] font-semibold mt-0.5">{statusLabel}</div>
        </div>
        {billing?.is_free ? null
          : !latestOrder
            ? <Link href="/purchase"><Button tone="primary" size="sm">ライセンス購入</Button></Link>
            : !hasActiveCharge
              ? <Link href="/me/balance"><Button tone="primary" size="sm">残高をチャージ</Button></Link>
              : null
        }
      </div>

      {/* Today KPIs */}
      <Card padded={false} className="mb-4">
        <CardHead right={<span className="font-mono text-[11px] text-text-dim">JST</span>}>
          Today · Live Operation
        </CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 px-5 py-6">
          <div>
            <Label>Last Settled PnL</Label>
            <div className="mt-1.5">
              <Money value={lastDeduction?.daily_profit ?? null} sign size="3xl" weight="bold"
                tone={Number(lastDeduction?.daily_profit ?? 0) >= 0 ? 'win' : 'lose'} />
            </div>
          </div>
          <div>
            <Label>Balance</Label>
            <div className="mt-1.5">
              {billing?.is_free
                ? <span className="text-xl font-semibold text-cyan">課金免除</span>
                : <Money value={Number(billing?.balance ?? 0)} size="2xl" weight="semibold" />}
            </div>
          </div>
          <div>
            <Label>Carry Loss</Label>
            <div className="mt-1.5">
              <Money value={Number(billing?.carry_loss ?? 0)} size="2xl" weight="semibold"
                tone={Number(billing?.carry_loss ?? 0) > 0 ? 'lose' : 'muted'} />
            </div>
          </div>
        </div>
      </Card>

      {/* Billing summary */}
      <Card padded={false} className="mb-4">
        <CardHead>Billing Summary</CardHead>
        <div className="grid grid-cols-2 sm:grid-cols-4 px-5 py-4">
          {[
            { label: 'Profit Share', value: billing ? `${(Number(billing.profit_share_rate) * 100).toFixed(0)}%` : '—' },
            { label: 'Total Charged', value: `$${Number(billing?.total_charged || 0).toFixed(2)}` },
            { label: 'Plan', value: billing?.is_free ? 'FREE' : 'Standard' },
            { label: 'Last Settled', value: lastDeduction?.date || '—' },
          ].map((it, i) => (
            <div key={it.label} className={i ? 'pl-4 border-l border-white/[0.07]' : ''}>
              <Label>{it.label}</Label>
              <div className="mt-1.5">
                <Money>{it.value}</Money>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Quick nav */}
      <Card padded={false}>
        <CardHead>Quick Navigation</CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-white/[0.05]">
          {[
            { href: '/me/realtime', title: 'ライブ運用状況', desc: '30 秒更新の PnL / 残高 / BET' },
            { href: '/me/balance', title: '残高・チャージ', desc: billing?.is_free ? '課金免除プラン適用中' : `現在 $${Number(billing?.balance || 0).toFixed(2)}` },
            { href: '/me/settlements', title: '日次精算履歴', desc: lastDeduction ? `最終: ${lastDeduction.date}` : '履歴なし' },
            { href: '/me/telegram', title: 'Telegram 連携', desc: '日次精算通知の受信' },
            { href: '/me/referral', title: '紹介プログラム', desc: '紹介 URL / 報酬の引出' },
            { href: '/me/support', title: 'サポート', desc: 'お問い合わせ' },
          ].map(c => (
            <Link key={c.href} href={c.href} className="bg-surface hover:bg-white/[0.03] px-5 py-4 transition group">
              <div className="flex items-start justify-between mb-1">
                <h3 className="text-sm font-semibold text-text">{c.title}</h3>
                <span className="text-text-dim group-hover:text-cyan transition text-xs">→</span>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">{c.desc}</p>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  )
}
