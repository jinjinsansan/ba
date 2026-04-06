import { createClient } from '@/lib/supabase-server'
import { redirect } from 'next/navigation'
import Link from 'next/link'

export default async function AdminPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/dashboard')

  const { count: userCount } = await supabase.from('profiles').select('*', { count: 'exact', head: true })
  const { count: pendingOrders } = await supabase.from('orders').select('*', { count: 'exact', head: true }).eq('status', 'pending')
  const { count: pendingCharges } = await supabase.from('charges').select('*', { count: 'exact', head: true }).eq('status', 'pending')
  const { count: openTickets } = await supabase.from('support_tickets').select('*', { count: 'exact', head: true }).eq('status', 'open')

  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-white font-semibold">Admin</Link>
            <Link href="/admin/orders" className="text-slate-400 hover:text-white">Orders</Link>
            <Link href="/admin/users" className="text-slate-400 hover:text-white">Users</Link>
            <Link href="/dashboard" className="text-slate-400 hover:text-white">My Dashboard</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-black mb-8">Admin Panel</h1>

        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <Link href="/admin/users" className="p-6 rounded-2xl bg-bg-card border border-white/5 hover:border-player/30 transition">
            <div className="text-3xl font-black text-player">{userCount || 0}</div>
            <div className="text-sm text-slate-400 mt-1">Total Users</div>
          </Link>
          <Link href="/admin/orders" className="p-6 rounded-2xl bg-bg-card border border-white/5 hover:border-yellow-500/30 transition">
            <div className="text-3xl font-black text-yellow-400">{pendingOrders || 0}</div>
            <div className="text-sm text-slate-400 mt-1">Pending Orders</div>
          </Link>
          <Link href="/admin/orders" className="p-6 rounded-2xl bg-bg-card border border-white/5 hover:border-yellow-500/30 transition">
            <div className="text-3xl font-black text-yellow-400">{pendingCharges || 0}</div>
            <div className="text-sm text-slate-400 mt-1">Pending Charges</div>
          </Link>
          <div className="p-6 rounded-2xl bg-bg-card border border-white/5">
            <div className="text-3xl font-black text-banker">{openTickets || 0}</div>
            <div className="text-sm text-slate-400 mt-1">Open Tickets</div>
          </div>
        </div>
      </div>
    </div>
  )
}
