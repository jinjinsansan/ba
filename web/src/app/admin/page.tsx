import { createAdminClient } from '@/lib/supabase-admin'
import Link from 'next/link'

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
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Admin Console</div>
        <h1 className="text-2xl sm:text-3xl font-hud">ダッシュボード</h1>
        <p className="text-text-muted text-sm mt-2">本日の運用サマリと未対応タスク</p>
      </div>

      {/* Today KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">本日 総 PnL</div>
          <div className={`text-2xl font-bold mt-1 ${todayTotalProfit >= 0 ? 'text-green-400' : 'text-banker'}`}>{todayTotalProfit >= 0 ? '+' : ''}${todayTotalProfit.toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">本日 総 手数料</div>
          <div className="text-2xl font-bold text-accent mt-1">${todayTotalFee.toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">未払い合計</div>
          <div className={`text-2xl font-bold mt-1 ${totalOutstanding > 0 ? 'text-yellow-400' : 'text-green-400'}`}>${totalOutstanding.toFixed(2)}</div>
        </div>
      </div>

      {/* Action queue */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Link href="/admin/users" className="p-5 rounded-xl glass-card hover:border-yellow-500/40 transition">
          <div className="text-3xl font-black text-player">{userCount || 0}</div>
          <div className="text-sm text-text-muted mt-1">総ユーザー数</div>
        </Link>
        <Link href="/admin/orders" className="p-5 rounded-xl glass-card hover:border-yellow-500/40 transition">
          <div className={`text-3xl font-black ${(pendingOrders || 0) > 0 ? 'text-yellow-400' : 'text-text-muted'}`}>{pendingOrders || 0}</div>
          <div className="text-sm text-text-muted mt-1">未確認注文</div>
        </Link>
        <Link href="/admin/orders" className="p-5 rounded-xl glass-card hover:border-yellow-500/40 transition">
          <div className={`text-3xl font-black ${(pendingCharges || 0) > 0 ? 'text-yellow-400' : 'text-text-muted'}`}>{pendingCharges || 0}</div>
          <div className="text-sm text-text-muted mt-1">未確認チャージ</div>
        </Link>
        <Link href="/admin/tickets" className="p-5 rounded-xl glass-card hover:border-yellow-500/40 transition">
          <div className={`text-3xl font-black ${(openTickets || 0) > 0 ? 'text-banker' : 'text-text-muted'}`}>{openTickets || 0}</div>
          <div className="text-sm text-text-muted mt-1">未対応チケット</div>
        </Link>
        <Link href="/admin/withdrawals" className="p-5 rounded-xl glass-card hover:border-yellow-500/40 transition">
          <div className={`text-3xl font-black ${(pendingWithdrawals || 0) > 0 ? 'text-green-400' : 'text-text-muted'}`}>{pendingWithdrawals || 0}</div>
          <div className="text-sm text-text-muted mt-1">出金申請</div>
        </Link>
        <Link href="/admin/users" className="p-5 rounded-xl glass-card hover:border-yellow-500/40 transition">
          <div className={`text-3xl font-black ${(suspendedUsers || 0) > 0 ? 'text-banker' : 'text-text-muted'}`}>{suspendedUsers || 0}</div>
          <div className="text-sm text-text-muted mt-1">サスペンド中</div>
        </Link>
      </div>
      {/* (note) /admin/ledger ページは廃止 (2026-05-17) */}

      {/* Recent signups */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-5 rounded-2xl glass-card">
          <h2 className="text-lg font-bold mb-3">最近のサインアップ</h2>
          {(recentSignups || []).length ? (
            <div className="space-y-2 text-sm">
              {(recentSignups || []).map(u => (
                <Link key={u.id} href={`/admin/users/${u.id}`} className="block border-t border-accent/10 pt-2 hover:bg-bg-glass rounded -mx-2 px-2 transition">
                  <div className="text-text font-semibold break-all">{u.email}</div>
                  <div className="text-xs text-text-dim">{new Date(u.created_at).toLocaleString('ja-JP')}</div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-text-muted text-sm">なし</p>
          )}
        </div>

        <div className="p-5 rounded-2xl glass-card">
          <h2 className="text-lg font-bold mb-3">最近のチャージ申請</h2>
          {(recentCharges || []).length ? (
            <div className="space-y-2 text-sm">
              {(recentCharges || []).map(c => (
                <Link key={c.id} href={`/admin/users/${c.user_id}`} className="block border-t border-accent/10 pt-2 hover:bg-bg-glass rounded -mx-2 px-2 transition">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-text font-bold">${Number(c.amount).toLocaleString()}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] ${c.status === 'confirmed' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{c.status}</span>
                  </div>
                  <div className="text-xs text-text-dim">{new Date(c.created_at).toLocaleString('ja-JP')}</div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-text-muted text-sm">なし</p>
          )}
        </div>
      </div>

      {/* Quick links */}
      <div className="p-5 rounded-2xl glass-soft border border-accent/10">
        <div className="text-xs text-text-muted mb-3">クイックリンク</div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link href="/admin/users" className="px-3 py-1.5 rounded-lg bg-bg-glass border border-accent/15 hover:border-accent/40 transition">ユーザー一覧</Link>
          <Link href="/admin/promos" className="px-3 py-1.5 rounded-lg bg-bg-glass border border-accent/15 hover:border-accent/40 transition">プロモコード</Link>
          <Link href="/admin/tickets" className="px-3 py-1.5 rounded-lg bg-bg-glass border border-accent/15 hover:border-accent/40 transition">チケット</Link>
        </div>
      </div>
    </div>
  )
}
