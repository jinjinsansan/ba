import { createClient } from '@/lib/supabase-server'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import UserRow from './UserRow'

export default async function AdminUsersPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/dashboard')

  const { data: users } = await supabase
    .from('profiles')
    .select('*, billing(*)')
    .order('created_at', { ascending: false })

  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-slate-400 hover:text-white">Admin</Link>
            <Link href="/admin/orders" className="text-slate-400 hover:text-white">Orders</Link>
            <Link href="/admin/users" className="text-white font-semibold">Users</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-black mb-8">User Management</h1>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-slate-500 text-left border-b border-white/10">
              <th className="pb-3">Email</th>
              <th className="pb-3">Balance</th>
              <th className="pb-3">Profit Share</th>
              <th className="pb-3">Status</th>
              <th className="pb-3">Referral</th>
              <th className="pb-3">Joined</th>
              <th className="pb-3">Actions</th>
            </tr></thead>
            <tbody>
              {users?.map(u => {
                const b = Array.isArray(u.billing) ? u.billing[0] : u.billing
                return <UserRow key={u.id} user={u} billing={b} />
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
