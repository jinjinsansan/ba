import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const { email, api_key } = await req.json()

  if (api_key !== process.env.LAPLACE_API_KEY) {
    return NextResponse.json({ ok: false, reason: 'Invalid API key' }, { status: 401 })
  }
  if (!email) {
    return NextResponse.json({ ok: false, reason: 'Email required' }, { status: 400 })
  }

  const admin = createAdminClient()

  // メールからユーザーを検索
  const { data: profile, error: profileError } = await admin
    .from('profiles')
    .select('id, email, is_admin')
    .eq('email', email.toLowerCase().trim())
    .single()

  if (profileError || !profile) {
    return NextResponse.json({ ok: false, reason: 'Account not found. Please check your email.' })
  }

  // 管理者は無条件で通過
  if (profile.is_admin) {
    const { data: billing } = await admin.from('billing').select('bot_config, gui_state').eq('user_id', profile.id).single()
    const { data: deliverables } = await admin
      .from('deliverables')
      .select('file_path, version, created_at')
      .eq('user_id', profile.id)
      .order('created_at', { ascending: false })
      .limit(1)
    const deliverable = Array.isArray(deliverables) && deliverables.length ? deliverables[0] : null
    return NextResponse.json({
      ok: true,
      bot_config: billing?.bot_config || {},
      gui_state: billing?.gui_state || {},
      deliverable: deliverable ? {
        url: deliverable.file_path,
        version: deliverable.version,
        updated_at: deliverable.created_at,
      } : null,
    })
  }

  // サブスクリプション確認
  const { data: billing } = await admin
    .from('billing')
    .select('bot_paid, balance, suspended, is_free, bot_config, gui_state, expires_at')
    .eq('user_id', profile.id)
    .single()

  if (!billing) {
    return NextResponse.json({ ok: false, reason: 'No subscription found. Please purchase a plan at bafather.uk' })
  }

  // 新料金モデル (2026-08-06): ロック条件は「サブスク期限」と「手動停止」のみ。
  // チャージ残高によるゲートは廃止(利益シェアは週次請求・未払い時はオーナーが手動停止)。
  if (billing.expires_at && new Date(billing.expires_at) < new Date()) {
    return NextResponse.json({ ok: false, reason: 'Your subscription has expired. Please renew at bafather.uk' })
  }

  if (!billing.bot_paid) {
    return NextResponse.json({ ok: false, reason: 'No active subscription. Please subscribe at bafather.uk' })
  }

  // 手動停止は is_free に関係なく全員に適用(新モデルでは全員 is_free になるため)
  if (billing.suspended) {
    return NextResponse.json({ ok: false, reason: 'Your account is suspended. Please contact admin.' })
  }
  const { data: deliverables } = await admin
    .from('deliverables')
    .select('file_path, version, created_at')
    .eq('user_id', profile.id)
    .order('created_at', { ascending: false })
    .limit(1)
  const deliverable = Array.isArray(deliverables) && deliverables.length ? deliverables[0] : null
  return NextResponse.json({
    ok: true,
    bot_config: billing.bot_config || {},
    gui_state: billing.gui_state || {},
    deliverable: deliverable ? {
      url: deliverable.file_path,
      version: deliverable.version,
      updated_at: deliverable.created_at,
    } : null,
  })
}
