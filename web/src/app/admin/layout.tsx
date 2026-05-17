import { createClient } from '@/lib/supabase-server'
import { redirect } from 'next/navigation'
import AdminRail from '@/components/ui/AdminRail'

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/')

  const { data: profile } = await supabase.from('profiles').select('email, is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) redirect('/me')

  return (
    <AdminRail userEmail={profile.email || user.email || ''}>
      {children}
    </AdminRail>
  )
}
