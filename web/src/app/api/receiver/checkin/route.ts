import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// 受け子アプリ (BACOPY / KBJAPAN / KBKOREA) の利用確認 — 2026-09-13
//
// アプリは bafather.uk のアカウントでログインし、START 前と稼働中に定期的にここへ問い合わせる。
//   - Authorization: Bearer <Supabase access token>
//   - body: { product: 'bacopy' | 'kbjapan' | 'kbkorea' }
// 判定は /api/auth/license と同じ新料金モデル (2026-08-06):
//   管理者は常に可 / サブスク期限切れ・未購入・手動停止は不可。
// あわせて billing.product に「どの版を使っているか」を記録し、管理者画面で3版を1つに管理する。

export const dynamic = 'force-dynamic'

const PRODUCTS = ['bacopy', 'kbjapan', 'kbkorea'] as const
type Product = (typeof PRODUCTS)[number]

function isProduct(v: unknown): v is Product {
  return typeof v === 'string' && (PRODUCTS as readonly string[]).includes(v)
}

export async function POST(req: NextRequest) {
  const auth = req.headers.get('authorization') || ''
  const token = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : ''
  if (!token) {
    return NextResponse.json({ ok: false, reason: 'Not signed in' }, { status: 401 })
  }

  let body: Record<string, unknown> = {}
  try {
    body = await req.json()
  } catch {
    body = {}
  }
  const product = String(body.product || '').trim().toLowerCase()

  const admin = createAdminClient()
  const { data: userData, error: userError } = await admin.auth.getUser(token)
  if (userError || !userData?.user) {
    return NextResponse.json({ ok: false, reason: 'Session expired. Please sign in again.' }, { status: 401 })
  }
  const userId = userData.user.id

  const { data: profile } = await admin
    .from('profiles')
    .select('email, is_admin')
    .eq('id', userId)
    .maybeSingle()

  const { data: billing } = await admin
    .from('billing')
    .select('bot_paid, suspended, is_free, expires_at, product')
    .eq('user_id', userId)
    .maybeSingle()

  // どの版を使っているかを記録 (billing 行がある利用者のみ。管理者画面の「版」表示に使う)
  if (billing && isProduct(product) && billing.product !== product) {
    await admin
      .from('billing')
      .update({ product, updated_at: new Date().toISOString() })
      .eq('user_id', userId)
  }

  const base = {
    email: profile?.email || userData.user.email || '',
    user_id: userId,
    is_admin: !!profile?.is_admin,
    product: isProduct(product) ? product : (billing?.product ?? null),
    is_free: !!billing?.is_free,
    expires_at: billing?.expires_at ?? null,
  }

  if (profile?.is_admin) {
    return NextResponse.json({ ok: true, ...base })
  }
  if (!billing) {
    return NextResponse.json({ ok: false, reason: 'No subscription found. Please subscribe at bafather.uk', ...base })
  }
  if (billing.expires_at && new Date(billing.expires_at) < new Date()) {
    return NextResponse.json({ ok: false, reason: 'Your subscription has expired. Please renew at bafather.uk', ...base })
  }
  if (!billing.bot_paid) {
    return NextResponse.json({ ok: false, reason: 'No active subscription. Please subscribe at bafather.uk', ...base })
  }
  if (billing.suspended) {
    return NextResponse.json({ ok: false, reason: 'Your account is suspended. Please contact admin.', ...base })
  }
  return NextResponse.json({ ok: true, ...base })
}
