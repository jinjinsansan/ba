import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

// オペレーターが「顧客の入金/ボーナス」を記録するエンドポイント。
// settle cron が残高差分フォールバックで課金する際、ここに記録された当日入金額を
// 差し引き、顧客が入金した自分の金に手数料を課さないようにする(2026-06-13)。
// daily_bet_pnl(ベット記録)で課金できる日は元々入金を含まないので影響しない。

function jstDate(d = new Date()) {
  return d.toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' })
}

async function requireAdmin() {
  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return { error: 'Unauthorized', status: 401 as const }
  const { data: profile } = await s.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return { error: 'Forbidden', status: 403 as const }
  return { user }
}

// POST { userId? , email? , amount , date? , note? } — 入金を1件記録する
export async function POST(req: NextRequest) {
  const auth = await requireAdmin()
  if ('error' in auth) return NextResponse.json({ error: auth.error }, { status: auth.status })

  const body = await req.json().catch(() => ({})) as {
    userId?: string; email?: string; amount?: number; date?: string; note?: string
  }
  const amount = Number(body.amount)
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json({ error: 'amount must be a positive number' }, { status: 400 })
  }
  const date = String(body.date || jstDate()).trim()

  const admin = createAdminClient()
  let userId = String(body.userId || '').trim()
  if (!userId && body.email) {
    const { data: prof } = await admin.from('profiles').select('id').eq('email', String(body.email).toLowerCase()).single()
    userId = String(prof?.id || '')
  }
  if (!userId) return NextResponse.json({ error: 'userId or known email required' }, { status: 400 })

  const { data, error } = await admin.from('deposits').insert({
    user_id: userId,
    amount: Math.round(amount * 100) / 100,
    date,
    note: String(body.note || ''),
    created_at: new Date().toISOString(),
  }).select('id').single()

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true, id: data?.id, user_id: userId, amount, date })
}

// GET ?date=YYYY-MM-DD — その日の記録済み入金一覧(確認用)
export async function GET(req: NextRequest) {
  const auth = await requireAdmin()
  if ('error' in auth) return NextResponse.json({ error: auth.error }, { status: auth.status })
  const date = req.nextUrl.searchParams.get('date') || jstDate()
  const admin = createAdminClient()
  const { data, error } = await admin.from('deposits').select('id, user_id, amount, date, note, created_at').eq('date', date)
  if (error) return NextResponse.json({ error: error.message, deposits: [] }, { status: 200 })
  return NextResponse.json({ date, deposits: data || [] })
}
