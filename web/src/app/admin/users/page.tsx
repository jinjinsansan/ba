import { createAdminClient } from '@/lib/supabase-admin'
import Link from 'next/link'

export const dynamic = 'force-dynamic'

type BillingLite = {
  balance?: number
  profit_share_rate?: number
  is_free?: boolean
  suspended?: boolean
  session_state?: Record<string, unknown> | null
}

type ProfileWithBilling = {
  id: string
  email: string
  is_admin?: boolean
  referral_code?: string | null
  created_at: string
  billing?: BillingLite | BillingLite[] | null
}

function bill(u: ProfileWithBilling): BillingLite | null {
  if (!u.billing) return null
  return Array.isArray(u.billing) ? (u.billing[0] || null) : u.billing
}

function todayPnl(b: BillingLite | null): number | null {
  if (!b?.session_state || typeof b.session_state !== 'object') return null
  const ss = b.session_state as Record<string, unknown>
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' })
  const dbp = typeof ss.daily_bet_pnl === 'number' && ss.daily_bet_pnl_date === today ? ss.daily_bet_pnl : null
  if (dbp !== null) return dbp
  const openBal = (ss.daily_open as { balance?: number } | undefined)?.balance
  const curBal = ss.current_balance
  if (typeof openBal === 'number' && typeof curBal === 'number') return curBal - openBal
  return null
}

export default async function AdminUsersPage() {
  const admin = createAdminClient()
  const { data: users } = await admin
    .from('profiles')
    .select('id, email, is_admin, referral_code, created_at, billing(balance, profit_share_rate, is_free, suspended, session_state)')
    .order('created_at', { ascending: false })

  const rows = (users || []) as ProfileWithBilling[]

  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Users</div>
        <h1 className="text-2xl sm:text-3xl font-hud">ユーザー一覧</h1>
        <p className="text-text-muted text-sm mt-2">クリックで個別ユーザーページへ ({rows.length} 名)</p>
      </div>

      <div className="overflow-x-auto glass-card p-4">
        <table className="min-w-[840px] w-full text-sm">
          <thead>
            <tr className="text-text-muted text-left border-b border-accent/10">
              <th className="pb-3 pr-4">メール</th>
              <th className="pb-3 pr-4">残高</th>
              <th className="pb-3 pr-4">当日 PnL</th>
              <th className="pb-3 pr-4">分配率</th>
              <th className="pb-3 pr-4">ステータス</th>
              <th className="pb-3 pr-4">登録日</th>
              <th className="pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(u => {
              const b = bill(u)
              const pnl = todayPnl(b)
              return (
                <tr key={u.id} className="border-b border-white/5 hover:bg-bg-glass transition">
                  <td className="py-3 pr-4">
                    <Link href={`/admin/users/${u.id}`} className="text-text hover:text-accent break-all">{u.email}</Link>
                    {u.is_admin && <span className="ml-2 text-[10px] text-yellow-400 bg-yellow-500/10 px-1.5 py-0.5 rounded">Admin</span>}
                  </td>
                  <td className="py-3 pr-4 font-bold">{b?.is_free ? '— FREE' : `$${Number(b?.balance || 0).toFixed(2)}`}</td>
                  <td className="py-3 pr-4 font-bold">
                    {pnl === null ? <span className="text-text-dim">—</span> : <span className={pnl >= 0 ? 'text-green-400' : 'text-banker'}>{pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</span>}
                  </td>
                  <td className="py-3 pr-4">{b ? `${(Number(b.profit_share_rate) * 100).toFixed(0)}%` : '—'}</td>
                  <td className="py-3 pr-4">
                    <div className="flex gap-1 flex-wrap">
                      {b?.suspended && <span className="text-[10px] bg-banker/20 text-banker px-1.5 py-0.5 rounded">Locked</span>}
                      {b?.is_free && <span className="text-[10px] bg-accent/20 text-accent px-1.5 py-0.5 rounded">Free</span>}
                      {!b?.suspended && !b?.is_free && <span className="text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded">Active</span>}
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-text-dim text-xs">{new Date(u.created_at).toLocaleDateString('ja-JP')}</td>
                  <td className="py-3">
                    <Link href={`/admin/users/${u.id}`} className="text-xs text-accent hover:underline">詳細 →</Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
