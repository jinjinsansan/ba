import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const { user_id, bot_config, api_key } = await req.json()

  if (api_key !== process.env.LAPLACE_API_KEY) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  if (!user_id || !bot_config) {
    return NextResponse.json({ error: 'Missing fields' }, { status: 400 })
  }

  const admin = createAdminClient()
  const { error } = await admin
    .from('billing')
    .upsert({ user_id, bot_config, updated_at: new Date().toISOString() }, { onConflict: 'user_id' })

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true })
}
