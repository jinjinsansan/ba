import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import TicketActions from './TicketActions'

export const dynamic = 'force-dynamic'

export default async function AdminTicketsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/dashboard')

  const admin = createAdminClient()
  const { data: tickets } = await admin
    .from('support_tickets')
    .select('*, profiles(email)')
    .order('created_at', { ascending: false })

  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-slate-400 hover:text-white">Admin</Link>
            <Link href="/admin/orders" className="text-slate-400 hover:text-white">Orders</Link>
            <Link href="/admin/users" className="text-slate-400 hover:text-white">Users</Link>
            <Link href="/admin/promos" className="text-slate-400 hover:text-white">Promos</Link>
            <Link href="/admin/tickets" className="text-white font-semibold">Tickets</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-black mb-8">Support Tickets</h1>
        <div className="space-y-4">
          {tickets?.map((t: any) => (
            <div key={t.id} className="p-6 rounded-2xl bg-bg-card border border-white/5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <span className="text-sm text-slate-400">{t.profiles?.email}</span>
                  <span className="text-xs text-slate-600 ml-3">{new Date(t.created_at).toLocaleString()}</span>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  t.status === 'open' ? 'bg-yellow-500/20 text-yellow-400' :
                  t.status === 'replied' ? 'bg-player/20 text-player' :
                  'bg-slate-500/20 text-slate-400'
                }`}>{t.status}</span>
              </div>
              <p className="text-white mb-3">{t.message}</p>
              {t.admin_reply && (
                <div className="p-3 rounded-lg bg-bg-primary border border-white/5 mb-3">
                  <div className="text-xs text-player mb-1">Admin Reply</div>
                  <p className="text-slate-300 text-sm">{t.admin_reply}</p>
                </div>
              )}
              <TicketActions ticketId={t.id} status={t.status} />
            </div>
          ))}
          {!tickets?.length && <p className="text-center text-slate-500 py-12">No tickets yet</p>}
        </div>
      </div>
    </div>
  )
}
