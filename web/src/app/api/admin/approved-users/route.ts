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
    .select('id, email, is_admin, created_at, billing(bot_paid, is_free, suspended, balance, grace_deadline, expires_at, product, updated_at)')
    .order('created_at', { ascending: false })

  if (error) {
    return NextResponse.json({ ok: false, reason: error.message }, { status: 500 })
  }

  const now = new Date()
  const users = (data || []).map((u: any) => {
    const b = Array.isArray(u.billing) ? u.billing[0] : u.billing
    // ステータス計算 (2026-09-23): 受け子アプリが実際に使う /api/receiver/checkin と同じ判定にそろえる。
    //   新料金モデル (2026-08-06): 管理者は常に可 / 期限 (expires_at) 切れ・未購入・停止は不可 / 残高は見ない。
    //   旧判定 (grace_deadline・残高0で empty_balance) のままだと、マスター画面の表示が GUI の実際の可否と食い違った。
    let status = 'not_approved'
    const expired = b?.expires_at && new Date(b.expires_at) < now
    if (u.is_admin) {
      status = 'admin'
    } else if (!b) {
      status = 'not_approved'
    } else if (expired) {
      status = 'expired'
    } else if (!b.bot_paid) {
      status = 'not_approved'
    } else if (b.suspended) {
      status = 'suspended'
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
      expires_at: b?.expires_at || null,
      product: b?.product || null,
      created_at: u.created_at,
      billing_updated_at: b?.updated_at || null,
    }
  })

  return NextResponse.json({ ok: true, users, fetched_at: new Date().toISOString() })
}
