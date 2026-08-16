import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// 招待コードの事前検証(サインアップ画面から呼ぶ)。
// - 実際の消費(uses+1)は DB トリガー enforce_invite_code が auth.users INSERT 時に行う。
//   ここは「無効なコードでは signUp を呼ばせない」ための UX 用ゲート。
// - invite_codes テーブルが未作成 / 参照エラー時は fail-closed(登録不可)。
// - 存在しないコードも存在するが無効なコードも同じ 'invalid' で返す(列挙対策)。
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({} as { code?: unknown }))
  const code = typeof body.code === 'string' ? body.code.trim().toUpperCase() : ''
  if (!code || code.length > 64) {
    return NextResponse.json({ ok: false, reason: 'invalid' }, { status: 400 })
  }

  const admin = createAdminClient()
  const { data, error } = await admin
    .from('invite_codes')
    .select('code, active, max_uses, uses, expires_at')
    .eq('code', code)
    .maybeSingle()

  if (error) {
    // テーブル未作成など。誰も通さない。
    return NextResponse.json({ ok: false, reason: 'unavailable' }, { status: 503 })
  }
  if (!data || !data.active) {
    return NextResponse.json({ ok: false, reason: 'invalid' }, { status: 403 })
  }
  if (data.expires_at && new Date(data.expires_at) < new Date()) {
    return NextResponse.json({ ok: false, reason: 'invalid' }, { status: 403 })
  }
  if (data.max_uses !== null && data.max_uses !== undefined && data.uses >= data.max_uses) {
    return NextResponse.json({ ok: false, reason: 'invalid' }, { status: 403 })
  }
  return NextResponse.json({ ok: true })
}
