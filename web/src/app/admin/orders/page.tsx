import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import OrderActions from './OrderActions'

export const dynamic = 'force-dynamic'

export default async function AdminOrdersPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/dashboard')

  const admin = createAdminClient()
  const { data: orders } = await admin
    .from('orders')
    .select('*, profiles(email)')
    .order('created_at', { ascending: false })

  const { data: charges } = await admin
    .from('charges')
    .select('*, profiles(email)')
    .order('created_at', { ascending: false })

  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-slate-400 hover:text-white">管理</Link>
            <Link href="/admin/orders" className="text-white font-semibold">注文</Link>
            <Link href="/admin/users" className="text-slate-400 hover:text-white">ユーザー</Link>
            <Link href="/admin/promos" className="text-slate-400 hover:text-white">プロモ</Link>
            <Link href="/admin/tickets" className="text-slate-400 hover:text-white">チケット</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-4">パッケージ注文</h2>
        <div className="overflow-x-auto mb-12">
          <table className="w-full text-sm">
            <thead><tr className="text-slate-500 text-left border-b border-white/10">
              <th className="pb-3">メール</th><th className="pb-3">プラン</th><th className="pb-3">金額</th><th className="pb-3">ネットワーク</th><th className="pb-3">プロモ</th><th className="pb-3">ステータス</th><th className="pb-3">日付</th><th className="pb-3">操作</th>
            </tr></thead>
            <tbody>
              {orders?.map((o: any) => (
                <tr key={o.id} className="border-b border-white/5">
                  <td className="py-3">{o.profiles?.email}</td>
                  <td className="py-3 capitalize">{o.plan}</td>
                  <td className="py-3 font-bold">${Number(o.amount).toLocaleString()}</td>
                  <td className="py-3">{o.usdt_network}</td>
                  <td className="py-3 text-slate-500">{o.promo_code || '—'}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      o.status === 'delivered' ? 'bg-green-500/20 text-green-400' :
                      o.status === 'confirmed' ? 'bg-player/20 text-player' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>{o.status === 'delivered' ? '配送済み' : o.status === 'confirmed' ? '確認済み' : o.status === 'sent' ? '送信済み' : '未確認'}</span>
                  </td>
                  <td className="py-3 text-slate-500">{new Date(o.created_at).toLocaleDateString('ja-JP')}</td>
                  <td className="py-3">
                    <OrderActions type="order" id={o.id} userId={o.user_id} status={o.status} />
                  </td>
                </tr>
              ))}
              {!orders?.length && <tr><td colSpan={8} className="py-6 text-center text-slate-500">注文はまだありません</td></tr>}
            </tbody>
          </table>
        </div>

        <h2 className="text-2xl font-bold mb-4">チャージ申請</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-slate-500 text-left border-b border-white/10">
              <th className="pb-3">メール</th><th className="pb-3">金額</th><th className="pb-3">ネットワーク</th><th className="pb-3">プロモ</th><th className="pb-3">ステータス</th><th className="pb-3">日付</th><th className="pb-3">操作</th>
            </tr></thead>
            <tbody>
              {charges?.map((c: any) => (
                <tr key={c.id} className="border-b border-white/5">
                  <td className="py-3">{c.profiles?.email}</td>
                  <td className="py-3 font-bold">${Number(c.amount).toLocaleString()}</td>
                  <td className="py-3">{c.usdt_network}</td>
                  <td className="py-3 text-slate-500">{c.promo_code || '—'}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${c.status === 'confirmed' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                      {c.status === 'confirmed' ? '確認済み' : '未確認'}
                    </span>
                  </td>
                  <td className="py-3 text-slate-500">{new Date(c.created_at).toLocaleDateString('ja-JP')}</td>
                  <td className="py-3">
                    <OrderActions type="charge" id={c.id} userId={c.user_id} status={c.status} amount={Number(c.amount)} />
                  </td>
                </tr>
              ))}
              {!charges?.length && <tr><td colSpan={7} className="py-6 text-center text-slate-500">チャージ申請はまだありません</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
