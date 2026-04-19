import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// bacopy Master からの一覧取得専用。LAPLACE_API_KEY で保護。
// Supabase profiles + billing を join して、承認ステータスを計算した配列を返す。
export async function POST(req: NextRequest) {
  const { api_key } = await req.json().catch(() => ({}))

  if (!api_key || api_key !== process.env.LAPLACE_API_KEY) {
    return NextResponse.json({ ok: false, reason: 'Invalid API key' }, { status: 401 })
  }

  const admin = createAdminClient()
  const { data, error } = await admin
    .from('profiles')
    .select('id, email, is_admin, created_at, billing(bot_paid, is_free, suspended, balance, grace_deadline, updated_at)')
    .order('created_at', { ascending: false })

  if (error) {
    return NextResponse.json({ ok: false, reason: error.message }, { status: 500 })
  }

  const now = new Date()
  const users = (data || []).map((u: any) => {
    const b = Array.isArray(u.billing) ? u.billing[0] : u.billing
    // ステータス計算: GUI 側 /api/auth/license のロジックと合わせる
    let status = 'not_approved'
    const expired = b?.grace_deadline && new Date(b.grace_deadline) < now
    if (u.is_admin) {
      status = 'admin'
    } else if (!b || !b.bot_paid) {
      status = 'not_approved'
    } else if (expired) {
      status = 'expired'
    } else if (b.suspended) {
      status = 'suspended'
    } else if (!b.is_free && (b.balance || 0) <= 0) {
      status = 'empty_balance'
    } else {
      status = 'approved'
    }

    return {
      email: u.email,
      is_admin: !!u.is_admin,
      status,
      bot_paid: !!b?.bot_paid,
      is_free: !!b?.is_free,
      suspended: !!b?.suspended,
      balance: b?.balance || 0,
      grace_deadline: b?.grace_deadline || null,
      created_at: u.created_at,
      billing_updated_at: b?.updated_at || null,
    }
  })

  return NextResponse.json({ ok: true, users, fetched_at: new Date().toISOString() })
}
