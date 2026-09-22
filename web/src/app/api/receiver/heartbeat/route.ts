import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// 受け子アプリ (BACOPY / KBJAPAN / KBKOREA) の生存報告 — 2026-09-22
//
// 受け子 GUI はログイン中、1 分ごとにここへ送る (表示専用)。
//   - Authorization: Bearer <Supabase access token>  (本人のトークン。共通キーは使わない)
//   - body: { product, executor_id, engine_running, app_version, engine_sha, os,
//             table_name, balance, bets_today, wins_today, losses_today, ties_today,
//             bet_errors_today, last_bet_at, payload }
// receiver_status に (user_id, product, executor_id) で上書きする。
// 管理画面の全受け子一覧・稼働ドット、ユーザー画面の「GUI 稼働中」がこれを読む。
// ★利用可否の判定はしない (それは /api/receiver/checkin)。ここで失敗しても受け子は止まらない。

export const dynamic = 'force-dynamic'

const PRODUCTS = ['bacopy', 'kbjapan', 'kbkorea'] as const

function str(v: unknown, max = 120): string | null {
  if (v === null || v === undefined) return null
  const s = String(v).trim()
  return s ? s.slice(0, max) : null
}
function num(v: unknown): number | null {
  // null / 未送信 / 空文字は「不明」。Number(null) = 0 なので先に弾く (残高が $0.00 と誤表示されていた)
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}
function int(v: unknown): number | null {
  const n = num(v)
  return n === null ? null : Math.max(0, Math.min(1_000_000, Math.round(n)))
}
function iso(v: unknown): string | null {
  if (!v) return null
  const d = new Date(String(v))
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
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

  const admin = createAdminClient()
  const { data: userData, error: userError } = await admin.auth.getUser(token)
  if (userError || !userData?.user) {
    return NextResponse.json({ ok: false, reason: 'Session expired' }, { status: 401 })
  }

  // payload は表示用の補足。大きすぎるものは捨てる (1 行を小さく保つ)
  let payload: Record<string, unknown> = {}
  if (body.payload && typeof body.payload === 'object' && !Array.isArray(body.payload)) {
    const s = JSON.stringify(body.payload)
    if (s.length <= 4000) payload = body.payload as Record<string, unknown>
  }

  const row = {
    user_id: userData.user.id,
    product,
    executor_id: str(body.executor_id, 60) || '',
    email: userData.user.email || null,
    last_seen_at: new Date().toISOString(),
    engine_running: !!body.engine_running,
    app_version: str(body.app_version, 40),
    engine_sha: str(body.engine_sha, 16),
    os: str(body.os, 40),
    table_name: str(body.table_name, 80),
    balance: num(body.balance),
    bets_today: int(body.bets_today),
    wins_today: int(body.wins_today),
    losses_today: int(body.losses_today),
    ties_today: int(body.ties_today),
    bet_errors_today: int(body.bet_errors_today),
    last_bet_at: iso(body.last_bet_at),
    payload,
  }

  const { error } = await admin.from('receiver_status').upsert(row, { onConflict: 'user_id,product,executor_id' })
  if (error) return NextResponse.json({ ok: false, reason: error.message }, { status: 500 })
  return NextResponse.json({ ok: true })
}
