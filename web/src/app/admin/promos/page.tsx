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

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl sm:text-3xl font-black font-hud">プロモコード</h1>
        </div>

        <PromoActions promos={promos || []} />
      </div>
    </div>
  )
}
