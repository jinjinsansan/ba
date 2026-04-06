import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import WithdrawalActions from './WithdrawalActions'

export const dynamic = 'force-dynamic'

export default async function AdminWithdrawalsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/dashboard')

  const admin = createAdminClient()
  const { data: withdrawals } = await admin
    .from('referral_withdrawals')
    .select('*, profiles(email)')
    .order('created_at', { ascending: false })

  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-slate-400 hover:text-white">管理</Link>
            <Link href="/admin/orders" className="text-slate-400 hover:text-white">注文</Link>
            <Link href="/admin/users" className="text-slate-400 hover:text-white">ユーザー</Link>
            <Link href="/admin/promos" className="text-slate-400 hover:text-white">プロモ</Link>
            <Link href="/admin/tickets" className="text-slate-400 hover:text-white">チケット</Link>
            <Link href="/admin/withdrawals" className="text-white font-semibold">出金申請</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-black mb-8">出金申請管理</h1>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-left border-b border-white/10">
                <th className="pb-3">ユーザー</th>
                <th className="pb-3">金額</th>
                <th className="pb-3">ネットワーク</th>
                <th className="pb-3">ウォレット</th>
                <th className="pb-3">ステータス</th>
                <th className="pb-3">申請日</th>
                <th className="pb-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {withdrawals?.map((w: any) => (
                <tr key={w.id} className="border-b border-white/5">
                  <td className="py-3">{w.profiles?.email || w.user_id}</td>
                  <td className="py-3 font-bold text-green-400">${Number(w.amount).toFixed(2)}</td>
                  <td className="py-3 text-slate-400">{w.network}</td>
                  <td className="py-3 font-mono text-xs text-slate-500 max-w-[160px] truncate">{w.wallet_address}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      w.status === 'approved' ? 'bg-green-500/20 text-green-400' :
                      w.status === 'rejected' ? 'bg-banker/20 text-banker' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {w.status === 'approved' ? '承認済' : w.status === 'rejected' ? '却下' : '申請中'}
                    </span>
                  </td>
                  <td className="py-3 text-slate-500">{new Date(w.created_at).toLocaleDateString('ja-JP')}</td>
                  <td className="py-3">
                    {w.status === 'pending' && <WithdrawalActions id={w.id} />}
                  </td>
                </tr>
              ))}
              {!withdrawals?.length && (
                <tr><td colSpan={7} className="py-8 text-center text-slate-500">申請はありません</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
