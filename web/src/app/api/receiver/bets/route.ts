import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// 受け子の BET 履歴の受け取り — 2026-09-22 (ダッシュボード段階2)
//
// 受け子 GUI が「Stake が受理して決済された勝負」を送る。通信が切れていた間の分はまとめて送られる。
//   - Authorization: Bearer <Supabase access token>  (本人のトークン)
//   - body: { product, executor_id, bets: [{ client_id, occurred_at, table_name, side, amount,
//             result, outcome, pnl, balance_after }] }   (1回 最大 100 件)
// (user_id, client_id) が同じものは二重に入れない (再送しても安全)。
// ★表示専用。ここで失敗しても受け子は止まらない。

export const dynamic = 'force-dynamic'

const PRODUCTS = ['bacopy', 'kbjapan', 'kbkorea'] as const
const SIDES = ['player', 'banker', 'tie']
const OUTCOMES = ['win', 'lose', 'push']

function str(v: unknown, max = 120): string | null {
  if (v === null || v === undefined) return null
  const s = String(v).trim()
  return s ? s.slice(0, max) : null
}
function num(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

export async function POST(req: NextRequest) {
  const auth = req.headers.get('authorization') || ''
  const token = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : ''
  if (!token) return NextResponse.json({ ok: false, reason: 'Not signed in' }, { status: 401 })

  let body: Record<string, unknown> = {}
  try {
    body = await req.json()
  } catch {
    body = {}
  }
  const product = String(body.product || '').trim().toLowerCase()
  if (!(PRODUCTS as readonly string[]).includes(product)) {
    return NextResponse.json({ ok: false, reason: 'unknown product' }, { status: 400 })
  }
  const list = Array.isArray(body.bets) ? (body.bets as Record<string, unknown>[]).slice(0, 100) : []
  if (!list.length) return NextResponse.json({ ok: true, saved: 0 })

  const admin = createAdminClient()
  const { data: userData, error: userError } = await admin.auth.getUser(token)
  if (userError || !userData?.user) {
    return NextResponse.json({ ok: false, reason: 'Session expired' }, { status: 401 })
  }
  const executorId = str(body.executor_id, 60) || ''

  const rows = []
  for (const b of list) {
    const clientId = str(b.client_id, 120)
    const occurred = b.occurred_at ? new Date(String(b.occurred_at)) : null
    const outcome = String(b.outcome || '').toLowerCase()
    if (!clientId || !occurred || Number.isNaN(occurred.getTime()) || !OUTCOMES.includes(outcome)) continue
    const side = String(b.side || '').toLowerCase()
    const result = String(b.result || '').toLowerCase()
    rows.push({
      user_id: userData.user.id,
      product,
      executor_id: executorId,
      client_id: clientId,
      occurred_at: occurred.toISOString(),
      table_name: str(b.table_name, 80),
      side: SIDES.includes(side) ? side : null,
      amount: num(b.amount),
      result: SIDES.includes(result) ? result : null,
      outcome,
      pnl: num(b.pnl),
      balance_after: num(b.balance_after),
      source: 'gui',
    })
  }
  if (!rows.length) return NextResponse.json({ ok: true, saved: 0 })

  const { error } = await admin
    .from('receiver_bets')
    .upsert(rows, { onConflict: 'user_id,client_id', ignoreDuplicates: true })
  if (error) return NextResponse.json({ ok: false, reason: error.message }, { status: 500 })
  return NextResponse.json({ ok: true, saved: rows.length })
}
