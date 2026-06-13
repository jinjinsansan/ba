import { createAdminClient } from '@/lib/supabase-admin'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import UserRow from './UserRow'

export const dynamic = 'force-dynamic'

type BillingLite = {
  balance?: number
  profit_share_rate?: number
  is_free?: boolean
  bot_paid?: boolean
  suspended?: boolean
  bot_config?: Record<string, unknown> | null
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

export default async function AdminUsersPage() {
  const admin = createAdminClient()
  const { data: users } = await admin
    .from('profiles')
    .select('id, email, is_admin, referral_code, created_at, billing(balance, profit_share_rate, is_free, bot_paid, suspended, bot_config, session_state)')
    .order('created_at', { ascending: false })

  const rows = (users || []) as ProfileWithBilling[]

  return (
    <div>
      <PageHeader
        kicker="Admin · Users"
        title="ユーザー一覧"
        sub="ライセンス / チャージの無料・有料をユーザーごとに設定"
        right={<Pill tone="admin">{rows.length} 名</Pill>}
      />

      <Card padded={false} className="overflow-x-auto">
        <table className="min-w-[1100px] w-full text-sm px-5">
          <thead>
            <tr className="border-b border-white/[0.07]">
              {[
                ['Email / 稼働状況', 'left'],
                ['Balance', 'left'],
                ['Today PnL', 'left'],
                ['分配率', 'left'],
                ['Status', 'left'],
                ['Joined', 'left'],
                ['操作', 'left'],
              ].map(([h, a], i) => (
                <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal text-left'].join(' ')}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <UserRow key={u.id} user={u} billing={bill(u)} />
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
