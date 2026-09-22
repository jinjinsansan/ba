import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// マスター (VPS) の決済記録から BET 履歴を取り込む — 2026-09-23 (ダッシュボード段階2・韓国版)
//
// 韓国版 (KBKOREA) のデュアルラインエンジンは GUI に「実際に賭けた勝負」だけを区別して知らせないので、
// GUI からは送らない。代わりに韓国版マスターの決済済み指示 (受け子ごと・bet_id と損益付き) を
// VPS のスクリプトが定期的にここへ送る。
//   - 認証: x-payments-secret = PAYMENTS_WEBHOOK_SECRET、または Authorization: Bearer <CRON_SECRET>
//   - body: { product, executor_id, bets: [{ client_id, occurred_at, table_name, side, amount, result, outcome, pnl }] }
// 受け子 ID → 利用者は、受け子 GUI の生存報告 (receiver_status) で対応付ける。
// まだ生存報告が無い受け子は取り込まない (unmapped を返す。次回以降に再送されれば入る)。
// (user_id, client_id) が同じものは二重に入れない。

export const dynamic = 'force-dynamic'

const PRODUCTS = ['bacopy', 'kbjapan', 'kbkorea'] as const
const SIDES = ['player', 'banker', 'tie']
const OUTCOMES = ['win', 'lose', 'push']

function authorized(req: NextRequest): boolean {
  const pay = process.env.PAYMENTS_WEBHOOK_SECRET || ''
  const cron = process.env.CRON_SECRET || ''
  const h = req.headers.get('x-payments-secret') || ''
  const auth = req.headers.get('authorization') || ''
  if (pay && h && h === pay) return true
  if (cron && auth === `Bearer ${cron}`) return true
  return false
}
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
  if (!authorized(req)) return NextResponse.json({ ok: false, reason: 'unauthorized' }, { status: 401 })
  let body: Record<string, unknown> = {}
  try {
    body = await req.json()
  } catch {
    body = {}
  }
  const product = String(body.product || '').trim().toLowerCase()
  const executorId = str(body.executor_id, 60) || ''
  if (!(PRODUCTS as readonly string[]).includes(product) || !executorId) {
    return NextResponse.json({ ok: false, reason: 'product and executor_id required' }, { status: 400 })
  }
  const list = Array.isArray(body.bets) ? (body.bets as Record<string, unknown>[]).slice(0, 500) : []

  const admin = createAdminClient()
  const { data: owner } = await admin
    .from('receiver_status')
    .select('user_id')
    .eq('product', product)
    .eq('executor_id', executorId)
    .order('last_seen_at', { ascending: false })
    .limit(1)
    .maybeSingle()
  if (!owner?.user_id) return NextResponse.json({ ok: true, saved: 0, unmapped: true })
  if (!list.length) return NextResponse.json({ ok: true, saved: 0 })

  const rows = []
  for (const b of list) {
    const clientId = str(b.client_id, 120)
    const occurred = b.occurred_at ? new Date(String(b.occurred_at)) : null
    const outcome = String(b.outcome || '').toLowerCase()
    if (!clientId || !occurred || Number.isNaN(occurred.getTime()) || !OUTCOMES.includes(outcome)) continue
    const side = String(b.side || '').toLowerCase()
    const result = String(b.result || '').toLowerCase()
    rows.push({
      user_id: owner.user_id,
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
      balance_after: null,
      source: 'master',
    })
  }
  if (!rows.length) return NextResponse.json({ ok: true, saved: 0 })
  const { error } = await admin
    .from('receiver_bets')
    .upsert(rows, { onConflict: 'user_id,client_id', ignoreDuplicates: true })
  if (error) return NextResponse.json({ ok: false, reason: error.message }, { status: 500 })
  return NextResponse.json({ ok: true, saved: rows.length })
}
