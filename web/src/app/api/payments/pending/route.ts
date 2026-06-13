import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// VPSポーラー用: 保留中(未期限)の暗号決済注文一覧を返す。共有シークレット認証。
// ポーラーはこの expected_amount と TronGrid の着金額を照合する。
export async function GET(req: NextRequest) {
  const secret = req.headers.get('x-payments-secret') || req.nextUrl.searchParams.get('secret') || ''
  if (!process.env.PAYMENTS_WEBHOOK_SECRET || secret !== process.env.PAYMENTS_WEBHOOK_SECRET) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  const admin = createAdminClient()
  const { data, error } = await admin
    .from('crypto_payments')
    .select('id, user_id, kind, expected_amount, expires_at, created_at')
    .eq('status', 'pending')
    .gt('expires_at', new Date().toISOString())
    .order('created_at', { ascending: true })
  if (error) return NextResponse.json({ error: error.message, pending: [] }, { status: 200 })
  return NextResponse.json({ pending: (data || []).map(d => ({ ...d, expected_amount: Number(d.expected_amount) })) })
}
