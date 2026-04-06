import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const serverSupabase = await createServerSupabase()
  const { data: { user } } = await serverSupabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: profile } = await serverSupabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const { type, id, userId, amount } = await req.json()
  const admin = createAdminClient()

  if (type === 'order') {
    await admin.from('orders').update({ status: 'confirmed', confirmed_at: new Date().toISOString() }).eq('id', id)
    // Create billing record
    await admin.from('billing').upsert({
      user_id: userId,
      bot_paid: true,
      profit_share_rate: 0.20,
    }, { onConflict: 'user_id' })
  } else if (type === 'charge') {
    await admin.from('charges').update({ status: 'confirmed', confirmed_at: new Date().toISOString() }).eq('id', id)
    // Add to billing balance
    const { data: billing } = await admin.from('billing').select('balance, total_charged').eq('user_id', userId).single()
    const newBalance = (billing?.balance || 0) + (amount || 0)
    const newTotal = (billing?.total_charged || 0) + (amount || 0)
    await admin.from('billing').upsert({
      user_id: userId,
      balance: newBalance,
      total_charged: newTotal,
      updated_at: new Date().toISOString(),
    }, { onConflict: 'user_id' })
  }

  return NextResponse.json({ ok: true })
}
