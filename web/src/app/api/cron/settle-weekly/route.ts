import { createAdminClient } from '@/lib/supabase-admin'
import { sendCustomerTelegramMessage } from '@/lib/customer-telegram'
import { NextRequest, NextResponse } from 'next/server'

// 週次課金 cron (日曜 JST 実行想定)。
// 対象 = is_free の会員(週次課金モデル)。月〜土の純粋PnL(daily_pnl_log)を合算し、
// キャリー(繰越損)を相殺してから profit_share_rate% の請求書を発行する。
// すべて weekly_pnl に履歴として残す(carry_in/net/fee/carry_out を可視化)。
//
// 手動実行/再計算: GET /api/cron/settle-weekly?week_start=YYYY-MM-DD (その週を対象)
//   Authorization: Bearer <CRON_SECRET>

function r2(n: number) { return Math.round((Number(n) || 0) * 100) / 100 }
function jstDate(d: Date) { return d.toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' }) }
function addDays(iso: string, days: number) {
  const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + days); return d.toISOString().slice(0, 10)
}

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  const admin = createAdminClient()

  // 対象週を決める。既定 = 直近に終了した「月〜土」(=実行日が日曜の前提で前日が土曜)。
  const override = new URL(req.url).searchParams.get('week_start')
  let weekStart: string
  if (override && /^\d{4}-\d{2}-\d{2}$/.test(override)) {
    weekStart = override
  } else {
    const jstNow = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Tokyo' }))
    const sat = new Date(jstNow); sat.setDate(jstNow.getDate() - 1)        // 前日(=土曜想定)
    const satIso = jstDate(sat)
    weekStart = addDays(satIso, -5)                                        // 月曜
  }
  const weekEnd = addDays(weekStart, 5)                                    // 土曜

  // 対象ユーザー = is_free かつ suspended=false。
  const { data: billings } = await admin
    .from('billing')
    .select('user_id, profit_share_rate, carry_loss, is_free, suspended, bot_config')
    .eq('is_free', true)
    .eq('suspended', false)
  if (!billings?.length) {
    return NextResponse.json({ ok: true, message: 'no free users', week_start: weekStart, week_end: weekEnd })
  }

  const userIds = billings.map(b => String(b.user_id)).filter(Boolean)
  const [{ data: profs }, { data: dpl }, { data: deps }] = await Promise.all([
    admin.from('profiles').select('id, email').in('id', userIds),
    admin.from('daily_pnl_log').select('user_id, date, bet_pnl, balance').gte('date', weekStart).lte('date', weekEnd).in('user_id', userIds)
      .then(r => r, () => ({ data: [] as Record<string, unknown>[] })),
    admin.from('deposits').select('user_id, amount').gte('date', weekStart).lte('date', weekEnd).in('user_id', userIds)
      .then(r => r, () => ({ data: [] as Record<string, unknown>[] })),
  ])
  const emailById = new Map<string, string>()
  for (const p of (profs || [])) emailById.set(String(p.id), String(p.email || ''))

  // ユーザーごとに 月〜土 を集計。
  type Agg = { gross: number; startBal: number | null; endBal: number | null; startDate: string; endDate: string; deposit: number }
  const agg = new Map<string, Agg>()
  for (const row of ((dpl as Record<string, unknown>[]) || [])) {
    const uid = String(row.user_id)
    const date = String(row.date)
    const pnl = Number(row.bet_pnl) || 0
    const bal = typeof row.balance === 'number' ? row.balance : null
    const a = agg.get(uid) || { gross: 0, startBal: null, endBal: null, startDate: '', endDate: '', deposit: 0 }
    a.gross = r2(a.gross + pnl)
    if (!a.startDate || date < a.startDate) { a.startDate = date; a.startBal = bal }
    if (!a.endDate || date > a.endDate) { a.endDate = date; a.endBal = bal }
    agg.set(uid, a)
  }
  for (const d of ((deps as Record<string, unknown>[]) || [])) {
    const uid = String(d.user_id); const amt = Number(d.amount) || 0
    const a = agg.get(uid); if (a) a.deposit = r2(a.deposit + amt)
  }

  const site = (process.env.NEXT_PUBLIC_SITE_URL || 'https://www.bafather.uk').replace(/\/$/, '')
  let billed = 0, noFee = 0, skipped = 0, invoiced = 0
  const results: Array<Record<string, unknown>> = []

  for (const b of billings) {
    const uid = String(b.user_id)
    const a = agg.get(uid)
    if (!a) { skipped++; continue } // その週にPnLログが無い

    // 既に確定済みならスキップ(二重課金防止)。
    const { data: existing } = await admin.from('weekly_pnl').select('id').eq('user_id', uid).eq('week_start', weekStart).maybeSingle()
    if (existing?.id) { skipped++; continue }

    const gross = r2(a.gross)
    const carryIn = r2(Number(b.carry_loss) || 0)           // 負債は負の値
    const net = r2(gross + carryIn)
    const rate = Math.min(1, Math.max(0, Number(b.profit_share_rate) || 0))
    const fee = net > 0 ? r2(net * rate) : 0
    const carryOut = net > 0 ? 0 : net                      // 負け→繰越(負)
    const status = fee > 0 ? 'billed' : 'no_fee'

    // 検算(情報): 実残高変化 − 純PnL − 入金 (出金は未トラッキング・差として現れる)。
    let reconcileDelta: number | null = null
    if (a.startBal !== null && a.endBal !== null) {
      reconcileDelta = r2((a.endBal - a.startBal) - gross - a.deposit)
    }
    const reconcileOk = reconcileDelta === null ? null : Math.abs(reconcileDelta) <= Math.max(1, Math.abs(gross) * 0.05)

    // 請求書発行(fee>0)。
    let invoiceId: string | null = null
    if (fee > 0) {
      const memo = `週次精算 ${weekStart}〜${weekEnd} / 純PnL $${gross.toFixed(2)}${carryIn !== 0 ? ` + 繰越 $${carryIn.toFixed(2)}` : ''} = $${net.toFixed(2)} の ${(rate * 100).toFixed(0)}%`
      const { data: inv } = await admin.from('invoices').insert({
        user_id: uid, amount: fee, memo, status: 'unpaid',
      }).select('id').maybeSingle()
      invoiceId = inv?.id || null
      if (invoiceId) {
        invoiced++
        // Telegram 通知(連携済みのみ)。
        try {
          const cfg = (b.bot_config && typeof b.bot_config === 'object') ? b.bot_config as Record<string, unknown> : {}
          const chatId = String(cfg.customer_telegram_chat_id || '').trim()
          if (chatId) {
            await sendCustomerTelegramMessage(chatId,
              `<b>📩 週次請求書</b>\n対象: ${weekStart}〜${weekEnd}\n` +
              `純利益: <b>$${gross.toFixed(2)}</b>${carryIn !== 0 ? `\n繰越: $${carryIn.toFixed(2)}` : ''}\n` +
              `課金対象: $${net.toFixed(2)}\n手数料(${(rate * 100).toFixed(0)}%): <b>$${fee.toFixed(2)}</b>\n\n` +
              `マイページからお支払いください:\n${site}/me`)
          }
        } catch { /* ignore */ }
      }
    }

    // 週次履歴を記録。
    await admin.from('weekly_pnl').insert({
      user_id: uid, week_start: weekStart, week_end: weekEnd,
      gross_pnl: gross, carry_in: carryIn, net_pnl: net, fee_rate: rate,
      fee_amount: fee, carry_out: carryOut, invoice_id: invoiceId,
      reconcile_delta: reconcileDelta, reconcile_ok: reconcileOk,
      status, note: emailById.get(uid) || '',
    })

    // 繰越損を更新(週次モデルでは carry はここだけが更新する)。
    await admin.from('billing').update({ carry_loss: carryOut, updated_at: new Date().toISOString() }).eq('user_id', uid)

    if (fee > 0) billed++; else noFee++
    results.push({ email: emailById.get(uid), gross, carryIn, net, rate, fee, carryOut, invoiceId, reconcileDelta })
  }

  // 管理者向け Telegram サマリ。
  try {
    const token = process.env.ADMIN_TELEGRAM_BOT_TOKEN
    const chatId = process.env.ADMIN_TELEGRAM_CHAT_ID
    if (token && chatId) {
      await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, parse_mode: 'HTML',
          text: `<b>週次精算</b> ${weekStart}〜${weekEnd}\n請求発行: ${invoiced}\n課金有: ${billed} / 課金無: ${noFee} / skip: ${skipped}` }),
      })
    }
  } catch { /* ignore */ }

  return NextResponse.json({ ok: true, week_start: weekStart, week_end: weekEnd, billed, noFee, skipped, invoiced, results })
}
