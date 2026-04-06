import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import PromoActions from './PromoActions'

export const dynamic = 'force-dynamic'

export default async function AdminPromosPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/dashboard')

  const admin = createAdminClient()
  const { data: promos } = await admin.from('promo_codes').select('*').order('created_at', { ascending: false })

  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-slate-400 hover:text-white">管理</Link>
            <Link href="/admin/orders" className="text-slate-400 hover:text-white">注文</Link>
            <Link href="/admin/users" className="text-slate-400 hover:text-white">ユーザー</Link>
            <Link href="/admin/promos" className="text-white font-semibold">プロモ</Link>
            <Link href="/admin/tickets" className="text-slate-400 hover:text-white">チケット</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-black">プロモコード</h1>
        </div>

        <PromoActions promos={promos || []} />
      </div>
    </div>
  )
}
