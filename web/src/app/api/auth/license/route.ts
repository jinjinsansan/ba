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
    const { data: billing } = await admin.from('billing').select('bot_config').eq('user_id', profile.id).single()
    return NextResponse.json({ ok: true, bot_config: billing?.bot_config || {} })
  }

  // サブスクリプション確認
  const { data: billing, error: billingError } = await admin
    .from('billing')
    .select('status, bot_config, expires_at')
    .eq('user_id', profile.id)
    .single()

  if (billingError || !billing) {
    return NextResponse.json({ ok: false, reason: 'No subscription found. Please purchase a plan at bafather.uk' })
  }

  if (billing.status !== 'active') {
    const statusMsg: Record<string, string> = {
      pending: 'Your subscription is pending confirmation. Please contact admin.',
      expired: 'Your subscription has expired. Please renew at bafather.uk',
      suspended: 'Your account has been suspended. Please contact admin.',
    }
    return NextResponse.json({
      ok: false,
      reason: statusMsg[billing.status] || `Subscription status: ${billing.status}`,
    })
  }

  // 有効期限チェック
  if (billing.expires_at && new Date(billing.expires_at) < new Date()) {
    return NextResponse.json({ ok: false, reason: 'Your subscription has expired. Please renew at bafather.uk' })
  }

  return NextResponse.json({
    ok: true,
    bot_config: billing.bot_config || {},
  })
}
