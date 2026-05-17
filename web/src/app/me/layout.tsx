import { createClient } from '@/lib/supabase-server'
import { redirect } from 'next/navigation'
import Rail from '@/components/ui/Rail'

export default async function MeLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/')

  const [{ data: profile }, { data: billing }] = await Promise.all([
    supabase.from('profiles').select('email, is_admin').eq('id', user.id).single(),
    supabase.from('billing').select('is_free, suspended').eq('user_id', user.id).single(),
  ])

  return (
    <Rail
      userEmail={profile?.email || user.email || ''}
      isAdmin={!!profile?.is_admin}
      isSuspended={!!billing?.suspended}
      isFree={!!billing?.is_free}
    >
      {children}
    </Rail>
  )
}
