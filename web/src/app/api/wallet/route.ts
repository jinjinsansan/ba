import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

// ウォレット登録・照会 (2026-08-06 新料金モデル / 突合 案A)。
// - GET:  自分のウォレット + 直近の照合履歴
// - POST: 登録(1ユーザー1アドレス・一度きり)。変更はサポート経由のみ
//         (RLS はユーザーの insert/update を許可していない — service_role で書く)。

const PATTERNS: Record<string, RegExp> = {
  tron: /^T[1-9A-HJ-NP-Za-km-z]{33}$/,
  bsc: /^0x[a-fA-F0-9]{40}$/,
}

export async function GET() {
  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: wallet } = await s.from('wallets')
    .select('network, address, status, recon_status, last_checked_at, created_at')
    .eq('user_id', user.id)
    .maybeSingle()

  if (!wallet) return NextResponse.json({ wallet: null, transfers: [] })

  const { data: transfers } = await s.from('chain_transfers')
    .select('tx_hash, direction, counterparty, amount_usdt, occurred_at, classified')
    .eq('user_id', user.id)
    .order('occurred_at', { ascending: false })
    .limit(10)

  return NextResponse.json({ wallet, transfers: transfers || [] })
}

export async function POST(req: NextRequest) {
  const s = await createServerSupabase()
  const { data: { user } } = await s.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json().catch(() => ({})) as { network?: string; address?: string }
  const network = body.network === 'bsc' ? 'bsc' : body.network === 'tron' ? 'tron' : null
  const address = String(body.address || '').trim()
  if (!network) return NextResponse.json({ error: 'network must be tron or bsc' }, { status: 400 })
  if (!PATTERNS[network].test(address)) {
    return NextResponse.json({ error: 'invalid address format' }, { status: 400 })
  }

  const admin = createAdminClient()

  const { data: existing } = await admin.from('wallets').select('id').eq('user_id', user.id).maybeSingle()
  if (existing) {
    // 変更はサポートでの本人確認が必要(UI にも明記)
    return NextResponse.json({ error: 'wallet already registered — contact support to change it' }, { status: 409 })
  }

  const { data, error } = await admin.from('wallets').insert({
    user_id: user.id,
    network,
    address,
  }).select('network, address, status, recon_status, created_at').single()

  if (error) {
    // unique(address) 違反 = 他ユーザーが同じアドレスを登録済み
    if (String(error.code) === '23505') {
      return NextResponse.json({ error: 'this address is already registered' }, { status: 409 })
    }
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true, wallet: data })
}
