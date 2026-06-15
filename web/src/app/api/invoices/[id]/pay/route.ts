import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

// ユーザーが請求書を「支払う」。ハイブリッド決済:
//   残高 >= 請求額  -> billing.balance から即引き落とし → invoice paid(ワンクリック完了)
//   残高 <  請求額  -> { needCharge:true } を返す。フロントは不足分を既存の
//                      USDT(TRC-20)自動チャージへ誘導 → 入金 → /api/payments/credit が
//                      unpaid invoices を自動消し込み(請求書が自動 paid になる)。
function r2(n: number) { return Math.round(n * 100) / 100 }

export async function POST(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params
  const invoiceId = String(id || '').trim()
  if (!invoiceId) return NextResponse.json({ error: 'invoice id required' }, { status: 400 })

  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const admin = createAdminClient()

  // 自分の未払い請求書のみ対象。
  const { data: inv } = await admin.from('invoices')
    .select('id, user_id, amount, status')
    .eq('id', invoiceId).maybeSingle()
  if (!inv || inv.user_id !== user.id) return NextResponse.json({ error: 'invoice not found' }, { status: 404 })
  if (inv.status !== 'unpaid') return NextResponse.json({ ok: true, already: true, status: inv.status })

  const amount = r2(Number(inv.amount) || 0)
  const { data: billing } = await admin.from('billing').select('balance').eq('user_id', user.id).maybeSingle()
  const balance = r2(Number(billing?.balance || 0))

  // 残高で賄えない → チャージ誘導(不足分)。
  if (balance < amount) {
    return NextResponse.json({
      ok: true, paid: false, needCharge: true,
      amount, balance, shortfall: r2(amount - balance),
    })
  }

  // 残高から即引き落とし。invoice を paid にする時だけ残高を減らす(二重決済防止に
  // status=unpaid のままの行を条件付き update)。
  const { data: claimed, error: claimErr } = await admin.from('invoices')
    .update({ status: 'paid', paid_via: 'balance', paid_at: new Date().toISOString(), updated_at: new Date().toISOString() })
    .eq('id', invoiceId).eq('status', 'unpaid')
    .select('id').maybeSingle()
  if (claimErr) return NextResponse.json({ error: claimErr.message }, { status: 500 })
  if (!claimed) return NextResponse.json({ ok: true, already: true }) // 競合(別タブで支払済)

  const { error: balErr } = await admin.from('billing').upsert(
    { user_id: user.id, balance: r2(balance - amount), updated_at: new Date().toISOString() },
    { onConflict: 'user_id' },
  )
  if (balErr) {
    // 残高更新に失敗したら invoice を unpaid に戻す(整合性保持)。
    await admin.from('invoices').update({ status: 'unpaid', paid_via: null, paid_at: null }).eq('id', invoiceId)
    return NextResponse.json({ error: 'balance debit failed: ' + balErr.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true, paid: true, paid_via: 'balance', amount, balance_after: r2(balance - amount) })
}
