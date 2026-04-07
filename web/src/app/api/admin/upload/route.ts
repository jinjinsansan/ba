import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

export const maxDuration = 60
export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  const serverSupabase = await createServerSupabase()
  const { data: { user } } = await serverSupabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: profile } = await serverSupabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const { userId, version = '1.0', url } = body

  if (!userId || !url) return NextResponse.json({ error: 'Missing userId or url' }, { status: 400 })

  const admin = createAdminClient()

  await admin.from('deliverables').delete().eq('user_id', userId)
  await admin.from('deliverables').insert({
    user_id: userId,
    file_path: url,
    version,
  })

  return NextResponse.json({ ok: true })
}
