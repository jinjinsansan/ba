import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const serverSupabase = await createServerSupabase()
  const { data: { user } } = await serverSupabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: profile } = await serverSupabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const formData = await req.formData()
  const file = formData.get('file') as File
  const userId = formData.get('userId') as string
  const version = formData.get('version') as string || '1.0'

  if (!file || !userId) return NextResponse.json({ error: 'Missing file or userId' }, { status: 400 })

  const admin = createAdminClient()
  const filePath = `${userId}/LAPLACE-v${version}.zip`

  const { error: uploadError } = await admin.storage
    .from('deliverables')
    .upload(filePath, file, { upsert: true })

  if (uploadError) return NextResponse.json({ error: uploadError.message }, { status: 500 })

  await admin.from('deliverables').upsert({
    user_id: userId,
    file_path: filePath,
    version,
  }, { onConflict: 'user_id' })

  return NextResponse.json({ ok: true, path: filePath })
}
