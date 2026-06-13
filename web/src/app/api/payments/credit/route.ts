import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// VPSポーラーが着金を検知したら呼ぶ。共有シークレット認証。
// tx_hash で冪等(同一送金で二重計上しない)・金額一致を検証してから反映:
//   kind=charge   -> billing.balance += amount (total_charged += amount), suspended=false
//   kind=license  -> billing.bot_paid = true, suspended=false
// 反映後は既存の停止/復旧ゲートが自動で稼働可否を判定する。
function r2(n: number) { return Math.round(n * 100) / 100 }

// 入金確認の Telegram 通知(専用Bot宛・共有チャンネルとは別)。失敗しても課金処理に波及させない。
async function notifyDeposit(text: string) {
  const token = process.env.PAYMENTS_TELEGRAM_BOT_TOKEN
  const chatId = process.env.PAYMENTS_TELEGRAM_CHAT_ID
  if (!token || !chatId) return
  try {
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML' }),
    })
  } catch { /* ignore */ }
}

export async function POST(req: NextRequest) {
  const secret = req.headers.get('x-payments-secret') || ''
  if (!process.env.PAYMENTS_WEBHOOK_SECRET || secret !== process.env.PAYMENTS_WEBHOOK_SECRET) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  const body = await req.json().catch(() => ({})) as { order_id?: string; tx_hash?: string; amount?: number }
  const orderId = String(body.order_id || '').trim()
  const txHash = String(body.tx_hash || '').trim()
  const amount = r2(Number(body.amount) || 0)
  if (!orderId || !txHash || amount <= 0) {
    return NextResponse.json({ error: 'order_id, tx_hash, amount required' }, { status: 400 })
  }

  const admin = createAdminClient()

  // 冪等: この tx_hash が既に処理済みなら何もしない
  const { data: dup } = await admin.from('crypto_payments').select('id, status').eq('tx_hash', txHash).maybeSingle()
  if (dup) return NextResponse.json({ ok: true, already: true, order_id: dup.id })

  // 注文を取得・検証
  const { data: order } = await admin
    .from('crypto_payments')
    .select('id, user_id, kind, expected_amount, status, expires_at')
    .eq('id', orderId)
    .maybeSingle()
  if (!order) return NextResponse.json({ error: 'order not found' }, { status: 404 })
  if (order.status !== 'pending') return NextResponse.json({ ok: true, already: true, order_id: order.id })
  if (r2(Number(order.expected_amount)) !== amount) {
    return NextResponse.json({ error: `amount mismatch (expected ${order.expected_amount}, got ${amount})` }, { status: 409 })
  }

  // 注文を「credited」へアトミックにクレーム(status=pending の時だけ成功)。
  // tx_hash UNIQUE 制約と合わせて二重計上を防ぐ。
  const { data: claimed, error: claimErr } = await admin
    .from('crypto_payments')
    .update({ status: 'credited', tx_hash: txHash, paid_amount: amount, credited_at: new Date().toISOString() })
    .eq('id', orderId)
    .eq('status', 'pending')
    .select('id')
    .maybeSingle()
  if (claimErr) return NextResponse.json({ error: claimErr.message }, { status: 500 })
  if (!claimed) return NextResponse.json({ ok: true, already: true, order_id: orderId })

  // billing へ反映
  const { data: billing } = await admin
    .from('billing')
    .select('balance, total_charged')
    .eq('user_id', order.user_id)
    .maybeSingle()

  if (order.kind === 'license') {
    const { error } = await admin.from('billing').upsert(
      { user_id: order.user_id, bot_paid: true, suspended: false, updated_at: new Date().toISOString() },
      { onConflict: 'user_id' },
    )
    if (error) return NextResponse.json({ error: 'license credit failed: ' + error.message }, { status: 500 })
  } else {
    // チャージ: まず未払いの日次手数料(daily_profit_invoices)を古い順に充当 → 残額を balance へ。
    // これをしないと、未払いがある状態でチャージしても GUI ゲート(unpaid invoice)が
    // 「支払い保留」で止まったままになり、自動再開しない(GUI連動の要)。
    let remaining = r2(Number(billing?.balance || 0) + amount)
    const newTotal = r2(Number(billing?.total_charged || 0) + amount)
    try {
      const { data: invs } = await admin
        .from('daily_profit_invoices')
        .select('id, outstanding_amount, paid_amount')
        .eq('user_id', order.user_id)
        .eq('status', 'unpaid')
        .gt('outstanding_amount', 0)
        .order('settle_date', { ascending: true })
      for (const inv of (invs || [])) {
        if (remaining <= 0) break
        const out = Number(inv.outstanding_amount) || 0
        const pay = Math.min(remaining, out)
        if (pay <= 0) continue
        const newOut = r2(out - pay)
        remaining = r2(remaining - pay)
        await admin.from('daily_profit_invoices').update({
          paid_amount: r2(Number(inv.paid_amount || 0) + pay),
          outstanding_amount: newOut,
          status: newOut <= 0 ? 'paid' : 'unpaid',
          updated_at: new Date().toISOString(),
        }).eq('id', inv.id)
      }
    } catch { /* daily_profit_invoices が無い環境ではスキップ(安全) */ }
    const { error } = await admin.from('billing').upsert(
      { user_id: order.user_id, balance: r2(remaining), total_charged: newTotal, suspended: false, updated_at: new Date().toISOString() },
      { onConflict: 'user_id' },
    )
    if (error) return NextResponse.json({ error: 'charge credit failed: ' + error.message }, { status: 500 })
  }

  // 入金確認の Telegram 通知(メール付き)
  try {
    const { data: prof } = await admin.from('profiles').select('email').eq('id', order.user_id).maybeSingle()
    const who = prof?.email || order.user_id
    const label = order.kind === 'license' ? 'ライセンス ($2000)' : `チャージ $${amount}`
    await notifyDeposit(
      `💰 <b>入金確認</b>\n` +
      `${who}\n` +
      `${label}\n` +
      `金額: <b>${amount} USDT</b>\n` +
      `tx: <code>${txHash}</code>`,
    )
  } catch { /* ignore */ }

  return NextResponse.json({ ok: true, credited: true, order_id: orderId, kind: order.kind, amount })
}
