import { createClient } from '@/lib/supabase-server'
import { NextResponse } from 'next/server'

export async function GET() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 })
  }
  const { data: billing } = await supabase
    .from('billing')
    .select('session_state, balance, is_free, suspended')
    .eq('user_id', user.id)
    .single()
  return NextResponse.json({
    session_state: billing?.session_state ?? null,
    bafather_balance: billing?.balance ?? null,
    is_free: !!billing?.is_free,
    suspended: !!billing?.suspended,
    fetched_at: new Date().toISOString(),
  })
}
