import Link from 'next/link'
import { createAdminClient } from '@/lib/supabase-admin'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'
import { Dot } from '@/components/ui/Dot'

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
  return Array.isArray(u.billing) ? u.billing[0] || null : u.billing
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

function isLive(b: BillingLite | null): boolean {
  if (!b?.session_state || typeof b.session_state !== 'object') return false
  const ss = b.session_state as Record<string, unknown>
  const lastAt = typeof ss.last_balance_at === 'string' ? new Date(ss.last_balance_at).getTime() : NaN
  if (!Number.isFinite(lastAt)) return false
  return Date.now() - lastAt < 90_000
}

export default async function AdminUsersPage() {
  const admin = createAdminClient()
  const { data: users } = await admin
    .from('profiles')
    .select('id, email, is_admin, referral_code, created_at, billing(balance, profit_share_rate, is_free, suspended, session_state)')
    .order('created_at', { ascending: false })

  const rows = (users || []) as ProfileWithBilling[]

  return (
    <div>
      <PageHeader
        kicker="Admin · Users"
        title="ユーザー一覧"
        sub="クリックで個別ユーザーページへ"
        right={<Pill tone="admin">{rows.length} 名</Pill>}
      />

      <Card padded={false} className="overflow-x-auto">
        <table className="min-w-[960px] w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.07]">
              {[
                ['Email', 'left'],
                ['Balance', 'right'],
                ['Today PnL', 'right'],
                ['Share', 'right'],
                ['Status', 'left'],
                ['Joined', 'left'],
                ['', 'right'],
              ].map(([h, a], i) => (
                <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((u, i) => {
              const b = bill(u)
              const pnl = todayPnl(b)
              const live = isLive(b)
              return (
                <tr key={u.id} className={i ? 'border-t border-white/[0.07]' : ''}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Dot tone={live ? 'win' : 'dim'} pulse={live} />
                      <Link href={`/admin/users/${u.id}`} className="text-cyan hover:underline break-all min-w-0">{u.email}</Link>
                      {u.is_admin && <Pill tone="admin">ADMIN</Pill>}
                    </div>
                    {(() => {
                      // フリート監視: 受け子エンジンが session_state.bot_status を60秒ごとに送る。
                      // 無ければ何も出さない(旧エンジンの受け子は後方互換で空)。
                      const bs = (b?.session_state as Record<string, any> | undefined)?.bot_status
                      if (!bs) return null
                      const moneyTxt = bs.money_mode === 'flat' ? `FLAT $${bs.unit}` : `SEQ ${bs.money_mode}`
                      const fol = bs.follow ? `追従ON${bs.follow_active ? ` x${bs.follow_chain}` : ''}` : '追従なし'
                      const over = bs.seq_overshoot
                      return (
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] font-mono">
                          <span className={bs.mode === 'auto' ? 'text-cyan' : 'text-text-muted'}>{bs.mode === 'auto' ? 'AUTO' : '手動'}</span>
                          <span className={bs.follow ? 'text-amber-400' : 'text-text-dim'}>{fol}</span>
                          <span className="text-text-muted">{moneyTxt}</span>
                          <span className="text-text-muted">NEXT ${bs.next_bet}</span>
                          {typeof over === 'number' && bs.money_mode !== 'flat' && (
                            <span className={over >= 6 ? 'text-rose-400 font-semibold' : over > 0 ? 'text-text-muted' : 'text-text-dim'}>負け越し▼{over}</span>
                          )}
                          <span className="text-text-dim">{bs.wins}W/{bs.losses}L{typeof bs.win_rate === 'number' ? ` ${bs.win_rate}%` : ''}</span>
                          {bs.loss_cut === 0 && bs.money_mode !== 'flat' && <span className="text-rose-400/80">⚠cut無制限</span>}
                        </div>
                      )
                    })()}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {b?.is_free
                      ? <span className="font-mono text-cyan text-sm">— FREE</span>
                      : <Money value={Number(b?.balance ?? 0)} size="md" weight="medium" />}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {pnl === null
                      ? <span className="text-text-dim">—</span>
                      : <Money value={pnl} sign size="md" weight="semibold" tone={pnl >= 0 ? 'win' : 'lose'} />}
                  </td>
                  <td className="px-5 py-3 text-right font-mono text-text-muted">
                    {b ? `${(Number(b.profit_share_rate) * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {b?.suspended && <Pill tone="danger">SUSPENDED</Pill>}
                      {b?.is_free && <Pill tone="free">FREE</Pill>}
                      {!b?.suspended && !b?.is_free && <Pill tone="live">ACTIVE</Pill>}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-text-muted font-mono text-xs">{new Date(u.created_at).toLocaleDateString('ja-JP')}</td>
                  <td className="px-5 py-3 text-right">
                    <Link href={`/admin/users/${u.id}`} className="text-text-dim hover:text-cyan">→</Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
