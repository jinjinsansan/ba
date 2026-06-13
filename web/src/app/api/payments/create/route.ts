import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

// ユーザーが「ライセンス($2000) / チャージ($X)」の暗号決済注文を作成する。
// USDT(TRC-20) を「ユニークな端数つき金額」で送ってもらい、VPSポーラーが着金を
// 金額照合で本人の注文に紐付ける(2026-06-13)。プロセッサ不要・鍵不要。
const LICENSE_PRICE = Number(process.env.LICENSE_PRICE_USDT || '2000')
const PAY_ADDRESS = process.env.PAYMENT_USDT_TRC20_ADDRESS || ''
const ORDER_TTL_MIN = Number(process.env.PAYMENT_ORDER_TTL_MIN || '60')

function r2(n: number) { return Math.round(n * 100) / 100 }

export async function POST(req: NextRequest) {
  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json().catch(() => ({})) as { kind?: string; amount?: number }
  const kind = body.kind === 'license' ? 'license' : 'charge'
  let base: number
  if (kind === 'license') {
    base = Math.floor(LICENSE_PRICE)
  } else {
    base = Math.floor(Number(body.amount) || 0)
    if (!Number.isFinite(base) || base <= 0) {
      return NextResponse.json({ error: 'amount must be a positive whole-dollar number' }, { status: 400 })
    }
  }
  if (!PAY_ADDRESS) {
    return NextResponse.json({ error: 'Payment address not configured (PAYMENT_USDT_TRC20_ADDRESS)' }, { status: 503 })
  }

  const admin = createAdminClient()
  const nowIso = new Date().toISOString()

  // 同一ベース額の保留注文が使っている端数を避けてユニークな金額を割り当てる。
  const { data: pend } = await admin
    .from('crypto_payments')
    .select('expected_amount')
    .eq('status', 'pending')
    .gt('expires_at', nowIso)
    .gte('expected_amount', base)
    .lt('expected_amount', base + 1)
  const usedCents = new Set<number>((pend || []).map(p => Math.round((Number(p.expected_amount) - base) * 100)))
  let cents = -1
  for (let c = 1; c <= 99; c++) { if (!usedCents.has(c)) { cents = c; break } }
  if (cents < 0) {
    return NextResponse.json({ error: 'Too many pending payments for this amount, try a slightly different amount' }, { status: 429 })
  }
  const expected = r2(base + cents / 100)
  const expiresAt = new Date(Date.now() + ORDER_TTL_MIN * 60_000).toISOString()

  const { data, error } = await admin.from('crypto_payments').insert({
    user_id: user.id,
    kind,
    expected_amount: expected,
    status: 'pending',
    expires_at: expiresAt,
  }).select('id, expected_amount, kind, expires_at').single()

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json({
    ok: true,
    order_id: data.id,
    kind: data.kind,
    amount: Number(data.expected_amount),     // この正確な額を送ってもらう
    token: 'USDT',
    network: 'TRC-20',
    address: PAY_ADDRESS,
    expires_at: data.expires_at,
  })
}
