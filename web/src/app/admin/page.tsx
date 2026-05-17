import { createAdminClient } from '@/lib/supabase-admin'
import Link from 'next/link'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader, Label } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'

export const dynamic = 'force-dynamic'

export default async function AdminPage() {
  const admin = createAdminClient()
  const jstDate = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' })

  const [
    { count: userCount },
    { count: pendingOrders },
    { count: pendingCharges },
    { count: openTickets },
    { count: pendingWithdrawals },
    { count: suspendedUsers },
    { data: todayDeductions },
    { data: outstandingInvoices },
    { data: recentSignups },
    { data: recentCharges },
  ] = await Promise.all([
    admin.from('profiles').select('*', { count: 'exact', head: true }),
    admin.from('orders').select('*', { count: 'exact', head: true }).eq('status', 'pending'),
    admin.from('charges').select('*', { count: 'exact', head: true }).eq('status', 'pending'),
    admin.from('support_tickets').select('*', { count: 'exact', head: true }).eq('status', 'open'),
    admin.from('referral_withdrawals').select('*', { count: 'exact', head: true }).eq('status', 'pending'),
    admin.from('billing').select('*', { count: 'exact', head: true }).eq('suspended', true),
    admin.from('deductions').select('daily_profit, fee_amount').eq('date', jstDate),
    admin.from('daily_profit_invoices').select('outstanding_amount').eq('status', 'unpaid'),
    admin.from('profiles').select('id, email, created_at').order('created_at', { ascending: false }).limit(5),
    admin.from('charges').select('id, user_id, amount, status, created_at').order('created_at', { ascending: false }).limit(5),
  ])

  const todayTotalProfit = (todayDeductions || []).reduce((s, d) => s + Number(d.daily_profit || 0), 0)
  const todayTotalFee = (todayDeductions || []).reduce((s, d) => s + Number(d.fee_amount || 0), 0)
  const totalOutstanding = (outstandingInvoices || []).reduce((s, i) => s + Number(i.outstanding_amount || 0), 0)

  return (
    <div>
      <PageHeader
        kicker="Admin · Dashboard"
        title="管理コンソール"
        sub="本日の運用サマリと未対応タスク"
        right={<Pill tone="admin">ADMIN</Pill>}
      />

      {/* Today KPI */}
      <Card padded={false} className="mb-4">
        <CardHead right={<span className="font-mono text-[11px] text-text-dim">JST {jstDate}</span>}>Today</CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-3 px-5 py-5">
          <div>
            <Label>本日 総 PnL</Label>
            <div className="mt-1.5"><Money value={todayTotalProfit} sign size="2xl" weight="bold" tone={todayTotalProfit >= 0 ? 'win' : 'lose'} /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>本日 総 手数料</Label>
            <div className="mt-1.5"><Money value={todayTotalFee} size="2xl" weight="bold" tone="cyan" /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>未払い合計</Label>
            <div className="mt-1.5"><Money value={totalOutstanding} size="2xl" weight="bold" tone={totalOutstanding > 0 ? 'warn' : 'win'} /></div>
          </div>
        </div>
      </Card>

      {/* Action queue */}
      <Card padded={false} className="mb-4">
        <CardHead>Action Queue</CardHead>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-px bg-white/[0.05]">
          {[
            { href: '/admin/users', label: '総ユーザー', count: userCount || 0, tone: 'cyan' as const },
            { href: '/admin/orders', label: '未確認注文', count: pendingOrders || 0, tone: (pendingOrders || 0) > 0 ? 'warn' : 'muted' as const },
            { href: '/admin/orders', label: '未確認チャージ', count: pendingCharges || 0, tone: (pendingCharges || 0) > 0 ? 'warn' : 'muted' as const },
            { href: '/admin/tickets', label: '未対応チケット', count: openTickets || 0, tone: (openTickets || 0) > 0 ? 'lose' : 'muted' as const },
            { href: '/admin/withdrawals', label: '出金申請', count: pendingWithdrawals || 0, tone: (pendingWithdrawals || 0) > 0 ? 'win' : 'muted' as const },
            { href: '/admin/users', label: 'サスペンド中', count: suspendedUsers || 0, tone: (suspendedUsers || 0) > 0 ? 'lose' : 'muted' as const },
          ].map(item => (
            <Link key={item.label} href={item.href} className="bg-surface hover:bg-white/[0.03] px-4 py-5 transition group">
              <Money value={item.count} size="2xl" weight="bold" tone={item.tone === 'muted' ? 'dim' : item.tone} />
              <div className="text-xs text-text-muted mt-1">{item.label}</div>
            </Link>
          ))}
        </div>
      </Card>

      {/* Recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card padded={false}>
          <CardHead>最近のサインアップ</CardHead>
          {(recentSignups || []).length ? (
            <div>
              {(recentSignups || []).map((u, i) => (
                <Link key={u.id} href={`/admin/users/${u.id}`} className={`block px-5 py-3 hover:bg-white/[0.03] transition ${i ? 'border-t border-white/[0.07]' : ''}`}>
                  <div className="text-text text-sm break-all">{u.email}</div>
                  <div className="font-mono text-[11px] text-text-dim mt-0.5">{new Date(u.created_at).toLocaleString('ja-JP')}</div>
                </Link>
              ))}
            </div>
          ) : <div className="px-5 py-6 text-text-muted text-sm">なし</div>}
        </Card>

        <Card padded={false}>
          <CardHead>最近のチャージ申請</CardHead>
          {(recentCharges || []).length ? (
            <div>
              {(recentCharges || []).map((c, i) => (
                <Link key={c.id} href={`/admin/users/${c.user_id}`} className={`block px-5 py-3 hover:bg-white/[0.03] transition ${i ? 'border-t border-white/[0.07]' : ''}`}>
                  <div className="flex items-center justify-between gap-2">
                    <Money value={Number(c.amount)} size="md" weight="bold" />
                    <Pill tone={c.status === 'confirmed' ? 'live' : c.status === 'rejected' ? 'danger' : 'warn'}>{c.status}</Pill>
                  </div>
                  <div className="font-mono text-[11px] text-text-dim mt-0.5">{new Date(c.created_at).toLocaleString('ja-JP')}</div>
                </Link>
              ))}
            </div>
          ) : <div className="px-5 py-6 text-text-muted text-sm">なし</div>}
        </Card>
      </div>
    </div>
  )
}
