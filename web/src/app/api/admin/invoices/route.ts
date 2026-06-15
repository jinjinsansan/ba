import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

// 管理者が任意の請求書を発行/取消する。
//   POST { userId, amount, memo }            -> 請求書を発行(status=unpaid)
//   POST { invoiceId, action: 'cancel' }     -> 未払い請求書を取消(status=canceled)
function r2(n: number) { return Math.round(n * 100) / 100 }

export async function POST(req: NextRequest) {
  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const { data: profile } = await s.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json().catch(() => ({})) as {
    userId?: string; amount?: number; memo?: string; invoiceId?: string; action?: string
  }
  const admin = createAdminClient()

  if (body.action === 'cancel') {
    const invoiceId = String(body.invoiceId || '').trim()
    if (!invoiceId) return NextResponse.json({ error: 'invoiceId required' }, { status: 400 })
    const { error } = await admin.from('invoices')
      .update({ status: 'canceled', updated_at: new Date().toISOString() })
      .eq('id', invoiceId).eq('status', 'unpaid')
    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json({ ok: true, canceled: invoiceId })
  }

  const userId = String(body.userId || '').trim()
  const amount = r2(Number(body.amount) || 0)
  const memo = String(body.memo || '').trim() || null
  if (!userId) return NextResponse.json({ error: 'userId required' }, { status: 400 })
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json({ error: 'amount must be a positive number' }, { status: 400 })
  }

  // 対象ユーザーの存在確認(誤発行防止)。
  const { data: target } = await admin.from('profiles').select('id, email').eq('id', userId).maybeSingle()
  if (!target) return NextResponse.json({ error: 'target user not found' }, { status: 404 })

  const { data, error } = await admin.from('invoices').insert({
    user_id: userId,
    amount,
    memo,
    status: 'unpaid',
    created_by: user.id,
  }).select('id, amount, memo, status, created_at').single()
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json({ ok: true, invoice: data, email: target.email })
}

// 管理者が特定ユーザーの請求書一覧を取得する(admin/users/[id] 表示用)。
export async function GET(req: NextRequest) {
  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const { data: profile } = await s.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const userId = new URL(req.url).searchParams.get('userId') || ''
  if (!userId) return NextResponse.json({ error: 'userId required' }, { status: 400 })
  const admin = createAdminClient()
  const { data, error } = await admin.from('invoices')
    .select('*').eq('user_id', userId).order('created_at', { ascending: false }).limit(50)
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true, invoices: data || [] })
}
